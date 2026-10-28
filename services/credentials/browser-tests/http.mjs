// Test-only receiver/server adapter. Verifier tokens and the ephemeral fixture key
// arrive over stdin, never files/arguments/logs. Production has no seeding route.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const {chromium} = createRequire(import.meta.url)(
  resolve(root, 'apps/web/node_modules/playwright'),
);
let input = '';
for await (const chunk of process.stdin) input += chunk;
const packet = JSON.parse(input);
let browser,
  page,
  phase = 'launch';
try {
  browser = await chromium.launch({headless: true});
  const context = await browser.newContext({serviceWorkers: 'block'});
  page = await context.newPage();
  let blocked = 0;
  await context.route('**/*', (route) => {
    if (new URL(route.request().url()).origin === packet.origin) return route.continue();
    blocked++;
    return route.abort();
  });
  // This binding models a receiver backend, not a browser-held integration token.
  await page.exposeFunction('receiver', async (service, op, body) => {
    assert.ok(['a', 'b'].includes(service) && ['challenge', 'verify'].includes(op));
    const endpoint = op === 'challenge' ? 'challenges' : 'verify';
    const response = await fetch(`${packet.origin}/v1/credentials/${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer ' + packet.receivers[service],
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(15000),
      redirect: 'error',
    });
    if (response.status !== 200) throw new Error('unexpected_http_status_' + response.status);
    return response.json();
  });
  phase = 'load';
  await page.goto(packet.origin);
  phase = 'http-issuance';
  const result = await page.evaluate(
    async (config) => {
      globalThis.testPhase = 'import';
      const sdk = await import('/holder.mjs');
      const raw = Uint8Array.from(atob(config.device_pkcs8), (c) => c.charCodeAt(0));
      const key = await globalThis.crypto.subtle.importKey(
        'pkcs8',
        raw,
        {name: 'ECDSA', namedCurve: 'P-256'},
        false,
        ['sign'],
      );
      raw.fill(0);
      delete config.device_pkcs8;
      const sid = config.expected.session_id;
      const path = '/v1/sessions/' + sid;
      const headers = {
        Authorization: config.session_authorization,
        'Content-Type': 'application/json',
      };
      const request = async (url, method, body, signal) => {
        const response = await fetch(url, {
          method,
          headers,
          body: body ? JSON.stringify(body) : undefined,
          signal,
          cache: 'no-store',
          credentials: 'omit',
          redirect: 'error',
        });
        if (response.status !== 200) throw new Error('unexpected_http_status_' + response.status);
        return response.json();
      };
      const counts = {authorize: 0, issue: 0, signs: 0};
      const bodies = [];
      globalThis.testPhase = 'source';
      const session = await sdk.createVerificationSession({
        result: await request(path + '/result', 'GET'),
        resultKey: config.result_key,
        credentialKey: config.credential_key,
        expected: config.expected,
        signDevice: async (message) => {
          counts.signs++;
          return sdk.webCryptoP256Signer(key)(message);
        },
        transport: {
          authorize: async (body, {signal}) => {
            counts.authorize++;
            return request(path + '/credential-authorization', 'POST', body, signal);
          },
          issue: async (body, {signal}) => {
            counts.issue++;
            bodies.push(JSON.stringify(body));
            const credential = await request(path + '/credential', 'POST', body, signal);
            if (counts.issue === 1) throw new Error('simulate-lost-response-after-server-commit');
            return credential;
          },
        },
      });
      globalThis.testPhase = 'consent';
      let refused, lost;
      try {
        await session.issue({consent: false});
      } catch (e) {
        refused = e.code;
      }
      if (refused !== 'holder_consent_required' || counts.authorize !== 0)
        throw new Error('consent_guard');
      globalThis.testPhase = 'first-issue';
      try {
        await session.issue({consent: true});
      } catch (e) {
        lost = e.code;
      }
      if (lost !== 'holder_request_failed') throw new Error('response_loss_guard');
      globalThis.testPhase = 'retry-issue';
      await session.issue({consent: true});
      const issued = session.metadata().state === 'issued';
      globalThis.testPhase = 'challenge';
      const a = await globalThis.receiver('a', 'challenge', {key_id: config.credential_key.key_id});
      const b = await globalThis.receiver('b', 'challenge', {key_id: config.credential_key.key_id});
      globalThis.testPhase = 'proof';
      const p1 = await session.present(a, {audience: 'https://service-a.example', consent: true});
      const p2 = await session.present(b, {audience: 'https://service-b.example', consent: true});
      globalThis.testPhase = 'verify';
      const ok1 = await globalThis.receiver('a', 'verify', p1);
      const replay = await globalThis.receiver('a', 'verify', p1);
      const ok2 = await globalThis.receiver('b', 'verify', p2);
      const anonymous = await fetch(path + '/result', {cache: 'no-store'});
      const wrongRole = await fetch('/v1/credentials/challenges', {
        method: 'POST',
        headers,
        body: '{}',
      });
      const serialized = JSON.stringify(p1);
      const hidden =
        !['account_id', 'device_id', 'source_result_id', 'source_purpose'].some(
          (name) => name in p1.disclosed,
        ) &&
        !serialized.includes(config.expected.account_id) &&
        !serialized.includes(config.expected.device_id);
      session.destroy();
      let closed;
      try {
        await session.issue({consent: true});
      } catch (e) {
        closed = e.code;
      }
      return {
        issued,
        valid: ok1.valid === true && ok2.valid === true,
        replay_rejected: replay.valid === false,
        pairwise: ok1.pseudonym !== ok2.pseudonym,
        hidden,
        same_request: bodies[0] === bodies[1],
        counts,
        anonymous_rejected: anonymous.status === 401,
        wrong_role_rejected: wrongRole.status === 401,
        closed: closed === 'holder_closed',
        storage_empty:
          globalThis.localStorage.length === 0 &&
          (await globalThis.indexedDB.databases()).length === 0,
      };
    },
    {
      expected: packet.expected,
      session_authorization: packet.session_authorization,
      device_pkcs8: packet.device_pkcs8,
      result_key: packet.result_key,
      credential_key: packet.credential_key,
    },
  );
  phase = 'assert';
  for (const [name, value] of Object.entries(result))
    if (name !== 'counts') assert.equal(value, true, name);
  assert.deepEqual(result.counts, {authorize: 1, issue: 2, signs: 1});
  assert.equal(blocked, 0);
  console.log(JSON.stringify({passed: true, counts: result.counts}));
} catch (error) {
  // Never print request/credential/key/exception payloads from browser or HTTP.
  const stage = await page?.evaluate(() => globalThis.testPhase).catch(() => 'unavailable');
  const code =
    String(error.message).match(/holder_[a-z_]+|unexpected_http_status_[0-9]+/)?.[0] ?? 'assertion';
  console.error('credential_browser_http_failed_at_' + phase + ':' + stage + ':' + code);
  process.exitCode = 1;
} finally {
  await browser?.close();
}
