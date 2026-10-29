import assert from 'node:assert/strict';
import {createHash, createPublicKey, generateKeyPairSync, sign, verify} from 'node:crypto';
import {createServer} from 'node:http';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {after, afterEach, before, beforeEach, test} from 'node:test';
import {issuerKeys, prepareHolder} from '../lib/bbs.mjs';
import {b64} from '../lib/profile.mjs';
import {issueVerification, VerificationVerifier} from '../lib/verification.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const {chromium} = createRequire(import.meta.url)(
  resolve(root, '../../apps/web/node_modules/playwright'),
);
const vector = JSON.parse(
  readFileSync(
    resolve(root, '../../packages/contracts/test-vectors/holder-source-public-v1.json'),
    'utf8',
  ),
);
const source = JSON.parse(Buffer.from(vector.result.payload, 'base64url'));
const keys = await issuerKeys();
const pin = {
  algorithm: 'BBS-BLS12-381-SHA-256-NYM',
  key_id: createHash('sha256').update(keys.publicKey).digest('hex'),
  public_key: b64(keys.publicKey),
};
const digest = (value) => createHash('sha256').update(value).digest('hex');
const canonical = (o) =>
  JSON.stringify(
    Object.fromEntries(
      Object.keys(o)
        .sort()
        .map((k) => [k, o[k]]),
    ),
  );
const claims = {
  protocol: 'vericlue-private-verification-v1',
  issuer: source.issuer,
  assurance: 'server-decision',
  verification_completed: true,
  valid_from: Math.floor(source.issued_at / 10) * 10,
  valid_until: Math.floor(source.expires_at / 10) * 10,
  policy_version: 'vericlue-session-result-v1',
  source_result_id: source.result_id,
  account_id: source.account_id,
  device_id: source.device_id,
  source_purpose: source.purpose,
};
let browser, server, origin, context, page;
const network = [];
const consoleOutput = [];

before(async () => {
  const bundle = readFileSync(resolve(root, 'dist/holder.mjs'));
  server = createServer((request, response) => {
    network.push(request.url);
    response.setHeader(
      'Content-Security-Policy',
      "default-src 'none'; script-src 'self'; connect-src 'none'; base-uri 'none'",
    );
    response.setHeader('Cache-Control', 'no-store');
    if (request.url === '/holder.mjs') {
      response.setHeader('Content-Type', 'application/javascript');
      response.end(bundle);
    } else if (request.url === '/') {
      response.setHeader('Content-Type', 'text/html');
      response.end('<!doctype html><title>Headless holder test</title>');
    } else {
      response.writeHead(404);
      response.end();
    }
  });
  await new Promise((done) => server.listen(0, '127.0.0.1', done));
  origin = 'http://127.0.0.1:' + server.address().port;
  browser = await chromium.launch({headless: true});
});

beforeEach(async () => {
  context = await browser.newContext({serviceWorkers: 'block'});
  await context.route('**/*', (route) => {
    const url = new URL(route.request().url());
    if (url.origin === origin && ['/', '/holder.mjs', '/favicon.ico'].includes(url.pathname))
      return route.continue();
    network.push('BLOCKED:' + url.origin);
    return route.abort();
  });
  page = await context.newPage();
  page.on('console', (message) => consoleOutput.push(message.text()));
  await page.goto(origin);
  await page.evaluate(async () => {
    globalThis.sdk = await import('/holder.mjs');
    Math.random = () => {
      throw new Error('Math.random must not be a crypto fallback');
    };
  });
});

afterEach(async () => {
  await context.close();
});
after(async () => {
  await browser?.close();
  if (server) await new Promise((done) => server.close(done));
  assert.ok(!network.some((url) => url.startsWith('BLOCKED:')));
  assert.ok(
    !consoleOutput.some(
      (line) => line.includes(source.account_id) || line.includes(source.device_id),
    ),
  );
});

async function initialize(options = {}) {
  return page.evaluate(
    async ({vector, pin, options}) => {
      globalThis.clockNow = vector.now;
      globalThis.wallet = await globalThis.sdk.createVerificationWallet({
        result: vector.result,
        resultKey: vector.result_key,
        credentialKey: pin,
        expected: vector.expected,
        clock: () => globalThis.clockNow,
        ...options,
      });
      globalThis.deviceKeys = await globalThis.crypto.subtle.generateKey(
        {name: 'ECDSA', namedCurve: 'P-256'},
        false,
        ['sign', 'verify'],
      );
      globalThis.signCalls = 0;
      return globalThis.wallet.metadata();
    },
    {vector, pin, options},
  );
}

function authorization(offer) {
  const value = {
    protocol: 'vericlue-credential-authorization-v1',
    session_id: source.session_id,
    source_result_id: source.result_id,
    account_id: source.account_id,
    device_id: source.device_id,
    offer_sha256: digest(Buffer.from(offer.commitment, 'base64url')),
    key_id: pin.key_id,
    expires_at: claims.valid_until,
    consent: true,
  };
  return {
    algorithm: 'ES256-DER',
    message: Buffer.from(canonical(value)).toString('base64'),
    expires_at: value.expires_at,
  };
}

async function prepare() {
  return page.evaluate(() => globalThis.wallet.prepare({consent: true}));
}

async function authorize(auth) {
  return page.evaluate(
    (auth) =>
      globalThis.wallet.authorize(auth, async (message) => {
        globalThis.signCalls++;
        return globalThis.sdk.webCryptoP256Signer(globalThis.deviceKeys.privateKey)(message);
      }),
    auth,
  );
}

async function issued() {
  await initialize();
  const offer = await prepare();
  const auth = authorization(offer),
    request = await authorize(auth);
  const spki = await page.evaluate(async () =>
    Array.from(
      new Uint8Array(
        await globalThis.crypto.subtle.exportKey('spki', globalThis.deviceKeys.publicKey),
      ),
    ),
  );
  assert.equal(
    verify(
      'sha256',
      Buffer.from(auth.message, 'base64'),
      createPublicKey({key: Buffer.from(spki), format: 'der', type: 'spki'}),
      Buffer.from(request.device_signature, 'base64'),
    ),
    true,
  );
  const credential = await issueVerification(keys, {commitment: offer.commitment}, claims);
  await page.evaluate((value) => globalThis.wallet.accept(value), credential);
  return {offer, credential};
}

const verifier = (audience) =>
  new VerificationVerifier({
    publicKey: keys.publicKey,
    issuer: claims.issuer,
    audience,
    clock: () => vector.now,
  });
const present = (q, options = {audience: q.audience, consent: true}) =>
  page.evaluate(({q, options}) => globalThis.wallet.present(q, options), {q, options});

test('actual Chromium: Python-signed result, P-256 consent, BBS issuance and pairwise proof interoperate', async () => {
  const {offer} = await issued();
  assert.deepEqual(Object.keys(offer).sort(), ['commitment', 'consent']);
  const a = verifier('https://a.example'),
    b = verifier('https://b.example');
  const p1 = await present(a.challenge()),
    p2 = await present(a.challenge()),
    p3 = await present(b.challenge());
  assert.equal(p1.pseudonym, p2.pseudonym);
  assert.notEqual(p1.pseudonym, p3.pseudonym);
  assert.notEqual(p1.proof, p2.proof);
  assert.equal((await a.verify(p1)).valid, true);
  assert.equal((await a.verify(p1)).valid, false);
  assert.equal((await b.verify(p3)).valid, true);
  assert.ok(!JSON.stringify(p1).includes(source.account_id));
  assert.ok(!JSON.stringify(p1).includes(source.device_id));
  const metadata = await page.evaluate(async () => ({
    keys: Object.keys(globalThis.wallet),
    json: JSON.stringify(globalThis.wallet),
    storage: globalThis.localStorage.length,
    databases: (await globalThis.indexedDB.databases()).length,
    exports: Object.keys(globalThis.sdk).sort(),
    buffer: typeof globalThis.Buffer,
  }));
  assert.deepEqual(metadata.keys, []);
  assert.equal(metadata.json, '{}');
  assert.equal(metadata.storage, 0);
  assert.equal(metadata.databases, 0);
  assert.equal(metadata.buffer, 'undefined');
  assert.deepEqual(metadata.exports, [
    'HolderError',
    'createVerificationSession',
    'createVerificationWallet',
    'webCryptoP256Signer',
  ]);
});

test('no offer or presentation without explicit boolean consent', async () => {
  await initialize();
  for (const consent of [false, 1, 'true', null]) {
    const code = await page.evaluate(async (consent) => {
      try {
        await globalThis.wallet.prepare({consent});
      } catch (e) {
        return e.code;
      }
    }, consent);
    assert.equal(code, 'holder_consent_required');
  }
  await issued();
  await assert.rejects(
    present(verifier('https://a.example').challenge(), {
      audience: 'https://a.example',
      consent: false,
    }),
  );
});

test('altered source signature, mismatched application context and untrusted pins fail before preparation', async () => {
  const bad = structuredClone(vector.result);
  bad.signature = (bad.signature.startsWith('A') ? 'B' : 'A') + bad.signature.slice(1);
  await assert.rejects(initialize({result: bad}));
  for (const key of Object.keys(vector.expected)) {
    await assert.rejects(initialize({expected: {...vector.expected, [key]: 'wrong-context'}}));
  }
  await assert.rejects(initialize({credentialKey: {...pin, key_id: '0'.repeat(64)}}));
  await assert.rejects(initialize({resultKey: {...vector.result_key, key_id: '0'.repeat(64)}}));
});

test('validly signed denial, excessive lifetime and missing account context are rejected', async () => {
  const pair = generateKeyPairSync('ed25519');
  const spki = pair.publicKey.export({format: 'der', type: 'spki'});
  const resultKey = {
    algorithm: 'Ed25519',
    public_key_spki: spki.toString('base64'),
    key_id: digest(spki),
  };
  for (const patch of [
    {status: 'deny'},
    {expires_at: source.issued_at + 61},
    {account_id: undefined, device_id: undefined},
  ]) {
    const payload = Buffer.from(canonical({...source, ...patch}));
    const result = {
      algorithm: 'Ed25519',
      key_id: resultKey.key_id,
      payload: b64(payload),
      signature: b64(
        sign(
          null,
          Buffer.concat([
            Buffer.from('vericlue-session-result-v1\0' + resultKey.key_id + '\0'),
            payload,
          ]),
          pair.privateKey,
        ),
      ),
    };
    await assert.rejects(initialize({result, resultKey}));
  }
});

test('every authorization field, extra whitespace and duplicate fields are checked before asking the device to sign', async () => {
  await initialize();
  const offer = await prepare(),
    auth = authorization(offer);
  const original = JSON.parse(Buffer.from(auth.message, 'base64'));
  for (const key of Object.keys(original)) {
    const value = {
      ...original,
      [key]: key === 'consent' ? false : key === 'expires_at' ? original[key] - 1 : 'wrong-context',
    };
    await assert.rejects(
      authorize({...auth, message: Buffer.from(canonical(value)).toString('base64')}),
    );
  }
  for (const raw of [
    ' ' + canonical(original),
    canonical(original).replace('"consent":true', '"consent":false,"consent":true'),
  ]) {
    await assert.rejects(authorize({...auth, message: Buffer.from(raw).toString('base64')}));
  }
  assert.equal(await page.evaluate(() => globalThis.signCalls), 0);
  await authorize(auth);
  assert.equal(await page.evaluate(() => globalThis.signCalls), 1);
});

test('a different holder commitment or mismatched credential cannot replace the consented issuance', async () => {
  await initialize();
  const offer = await prepare();
  await authorize(authorization(offer));
  const foreign = await prepareHolder();
  const foreignCredential = await issueVerification(keys, foreign.offer, claims);
  await assert.rejects(page.evaluate((c) => globalThis.wallet.accept(c), foreignCredential));
  const wrong = await issueVerification(
    keys,
    {commitment: offer.commitment},
    {...claims, account_id: 'acct_' + 'a'.repeat(32)},
  );
  await assert.rejects(page.evaluate((c) => globalThis.wallet.accept(c), wrong));
  const valid = await issueVerification(keys, {commitment: offer.commitment}, claims);
  const altered = {
    ...valid,
    signature: (valid.signature.startsWith('A') ? 'B' : 'A') + valid.signature.slice(1),
  };
  await assert.rejects(page.evaluate((c) => globalThis.wallet.accept(c), altered));
  await page.evaluate((c) => globalThis.wallet.accept(c), valid);
});

test('caller-approved audience and verifier-owned challenge policy/time cannot be substituted', async () => {
  await issued();
  const q = verifier('https://a.example').challenge();
  await assert.rejects(present(q, {audience: 'https://other.example', consent: true}));
  for (const patch of [
    {policy: 'adult'},
    {issued_at: vector.now + 1},
    {expires_at: vector.now},
    {expires_at: vector.now + 61},
    {nonce: 'A'.repeat(42) + 'B'},
  ])
    await assert.rejects(present({...q, ...patch}));
  const p = await present(q);
  assert.equal(p.challenge_id, q.id);
});

test('logout during a device prompt discards its result; closed wallets cannot produce offers or proofs', async () => {
  await initialize();
  const offer = await prepare(),
    auth = authorization(offer);
  await page.evaluate((auth) => {
    globalThis.pending = globalThis.wallet
      .authorize(
        auth,
        () =>
          new Promise((done) => {
            globalThis.resolveDevice = done;
          }),
      )
      .then(
        () => 'unexpected',
        (e) => e.code,
      );
  }, auth);
  await page.waitForFunction(() => typeof globalThis.resolveDevice === 'function');
  const result = await page.evaluate(async () => {
    globalThis.wallet.destroy();
    globalThis.resolveDevice(new Uint8Array([48, 6, 2, 1, 1, 2, 1, 1]));
    return {result: await globalThis.pending, metadata: globalThis.wallet.metadata()};
  });
  assert.equal(result.result, 'holder_closed');
  assert.deepEqual(result.metadata, {state: 'closed', expires_at: 0});
  await assert.rejects(prepare());
});

test('concurrent actions are bounded and source expiry closes the in-memory wallet', async () => {
  await initialize();
  const result = await page.evaluate(async () =>
    Promise.all([
      globalThis.wallet.prepare({consent: true}).then(() => 'ok'),
      globalThis.wallet.prepare({consent: true}).then(
        () => 'unexpected',
        (e) => e.code,
      ),
    ]),
  );
  assert.deepEqual(result, ['ok', 'holder_busy']);
  await page.evaluate((time) => {
    globalThis.clockNow = time;
  }, claims.valid_until);
  await assert.rejects(authorize(authorization({commitment: 'A'.repeat(235)})));
  assert.equal((await page.evaluate(() => globalThis.wallet.metadata())).state, 'closed');
});

test('logout or expiry while a proof is computing discards the proof', async () => {
  await issued();
  const q = verifier('https://a.example').challenge();
  const closed = await page.evaluate(async (q) => {
    const pending = globalThis.wallet.present(q, {audience: q.audience, consent: true}).then(
      () => 'unexpected',
      (e) => e.code,
    );
    globalThis.wallet.destroy();
    return pending;
  }, q);
  assert.equal(closed, 'holder_closed');
  await issued();
  const expired = await page.evaluate(
    async ({q, expiry}) => {
      const pending = globalThis.wallet.present(q, {audience: q.audience, consent: true}).then(
        () => 'unexpected',
        (e) => e.code,
      );
      globalThis.clockNow = expiry;
      return pending;
    },
    {q, expiry: claims.valid_until},
  );
  assert.equal(expired, 'holder_expired');
});

async function session(fault = '', requestTimeoutMs = 10000) {
  await initialize();
  const issued = new Map();
  await page.exposeFunction('holderApi', async (op, body) => {
    if (op === 'authorize') return authorization(body);
    if (!issued.has(body.commitment))
      issued.set(
        body.commitment,
        await issueVerification(keys, {commitment: body.commitment}, claims),
      );
    return issued.get(body.commitment);
  });
  await page.evaluate(
    async ({vector, pin, fault, requestTimeoutMs}) => {
      globalThis.fault = fault;
      globalThis.calls = {authorize: [], issue: [], aborted: 0};
      const invoke = async (op, body, {signal}) => {
        globalThis.calls[op].push(structuredClone(body));
        signal.addEventListener('abort', () => globalThis.calls.aborted++, {once: true});
        if (globalThis.fault === op + '_fail') {
          globalThis.fault = '';
          body.commitment = 'changed-by-transport';
          throw new Error('must-not-leak-bearer-or-response');
        }
        const result = await globalThis.holderApi(op, body);
        if (globalThis.fault === op + '_lost') {
          globalThis.fault = '';
          throw new Error('response-lost');
        }
        if (globalThis.fault === op + '_hang') {
          globalThis.fault = '';
          return new Promise((resolve) => {
            globalThis.resolveTransport = () => resolve(result);
          });
        }
        return result;
      };
      globalThis.session = await globalThis.sdk.createVerificationSession({
        result: vector.result,
        resultKey: vector.result_key,
        credentialKey: pin,
        expected: vector.expected,
        clock: () => globalThis.clockNow,
        requestTimeoutMs,
        signDevice: async (message) => {
          globalThis.signCalls++;
          return globalThis.sdk.webCryptoP256Signer(globalThis.deviceKeys.privateKey)(message);
        },
        transport: {
          authorize: (body, options) => invoke('authorize', body, options),
          issue: (body, options) => invoke('issue', body, options),
        },
      });
    },
    {vector, pin, fault, requestTimeoutMs},
  );
}

const issueSession = () => page.evaluate(() => globalThis.session.issue({consent: true}));

test('session orchestration retries authorization with the same unmodified commitment and explicit consent', async () => {
  await session('authorize_fail');
  const refused = await page.evaluate(async () => {
    try {
      await globalThis.session.issue({consent: false});
    } catch (e) {
      return e.code;
    }
  });
  assert.equal(refused, 'holder_consent_required');
  assert.equal(await page.evaluate(() => globalThis.calls.authorize.length), 0);
  const error = await page.evaluate(async () => {
    try {
      await globalThis.session.issue({consent: true});
    } catch (e) {
      return {code: e.code, message: e.message};
    }
  });
  assert.deepEqual(error, {code: 'holder_request_failed', message: 'holder_request_failed'});
  assert.equal((await issueSession()).state, 'issued');
  const calls = await page.evaluate(() => globalThis.calls);
  assert.deepEqual(calls.authorize[0], calls.authorize[1]);
  assert.equal(calls.issue.length, 1);
});

test('lost issuance response keeps the signed request; retry does not sign or blind-issue a new holder', async () => {
  await session('issue_lost');
  await assert.rejects(issueSession());
  assert.equal((await issueSession()).state, 'issued');
  assert.equal((await issueSession()).state, 'issued');
  const calls = await page.evaluate(() => ({
    ...globalThis.calls,
    signs: globalThis.signCalls,
    keys: Object.keys(globalThis.session),
  }));
  assert.equal(calls.authorize.length, 1);
  assert.equal(calls.signs, 1);
  assert.deepEqual(calls.issue[0], calls.issue[1]);
  assert.equal(calls.issue.length, 2);
  assert.deepEqual(calls.keys, []);
  const receiver = verifier('https://a.example');
  const q = receiver.challenge();
  const proof = await page.evaluate(
    (q) => globalThis.session.present(q, {audience: q.audience, consent: true}),
    q,
  );
  assert.equal((await receiver.verify(proof)).valid, true);
  assert.equal(proof.challenge_id, q.id);
});

test('HTTP callback timeout aborts its signal, keeps the pending issuance body and allows retry', async () => {
  await session('issue_hang', 1000);
  const code = await page.evaluate(async () => {
    try {
      await globalThis.session.issue({consent: true});
    } catch (e) {
      return e.code;
    }
  });
  assert.equal(code, 'holder_request_timeout');
  assert.equal((await issueSession()).state, 'issued');
  const calls = await page.evaluate(() => ({...globalThis.calls, signs: globalThis.signCalls}));
  assert.equal(calls.signs, 1);
  assert.deepEqual(calls.issue[0], calls.issue[1]);
  assert.ok(calls.aborted > 0);
});

test('destroy cancels an uncooperative transport and discards its late response; concurrent calls are refused', async () => {
  await session('authorize_hang');
  await page.evaluate(() => {
    globalThis.pendingSession = globalThis.session.issue({consent: true}).then(
      () => 'unexpected',
      (e) => e.code,
    );
  });
  await page.waitForFunction(() => typeof globalThis.resolveTransport === 'function');
  const result = await page.evaluate(async () => {
    let busy;
    try {
      await globalThis.session.issue({consent: true});
    } catch (e) {
      busy = e.code;
    }
    globalThis.session.destroy();
    const code = await globalThis.pendingSession;
    globalThis.resolveTransport();
    await new Promise((done) => setTimeout(done, 0));
    return {
      busy,
      code,
      state: globalThis.session.metadata().state,
      signs: globalThis.signCalls,
      issues: globalThis.calls.issue.length,
    };
  });
  assert.deepEqual(result, {
    busy: 'holder_busy',
    code: 'holder_closed',
    state: 'closed',
    signs: 0,
    issues: 0,
  });
});

test('expiry after an HTTP response closes the session before signing or issuing', async () => {
  await session('authorize_hang');
  await page.evaluate(() => {
    globalThis.pendingSession = globalThis.session.issue({consent: true}).then(
      () => 'unexpected',
      (e) => e.code,
    );
  });
  await page.waitForFunction(() => typeof globalThis.resolveTransport === 'function');
  const code = await page.evaluate(async (expiry) => {
    globalThis.clockNow = expiry;
    globalThis.resolveTransport();
    return globalThis.pendingSession;
  }, claims.valid_until);
  assert.equal(code, 'holder_expired');
  assert.equal(await page.evaluate(() => globalThis.signCalls), 0);
});
