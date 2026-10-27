import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {mkdtempSync, readFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, resolve, sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {test} from 'node:test';
import {issuerKeys, prepareHolder, issueBbs} from '../lib/bbs.mjs';
import {demoClaims} from '../lib/profile.mjs';
import {
  issueVerification,
  presentVerification,
  verifyVerification,
  VerificationVerifier,
} from '../lib/verification.mjs';

const NOW = Date.parse('2026-10-27T00:00:00Z') / 1000;
const keys = await issuerKeys();
const h = await prepareHolder();
const claims = {
  protocol: 'vericlue-private-verification-v1',
  issuer: 'https://vericlue.example',
  assurance: 'server-decision',
  verification_completed: true,
  valid_from: NOW,
  valid_until: NOW + 60,
  policy_version: 'vericlue-session-result-v1',
  source_result_id: 'res_' + 'a'.repeat(64),
  account_id: 'acct_' + 'b'.repeat(32),
  device_id: 'dev_' + 'c'.repeat(32),
  source_purpose: 'reauth',
};
const credential = await issueVerification(keys, h.offer, claims);
const create = (options) =>
  new VerificationVerifier({
    publicKey: keys.publicKey,
    issuer: claims.issuer,
    audience: 'https://service-a.example',
    clock: () => NOW,
    ...options,
  });

test('stateless crypto requires the stored challenge and pinned issuer/audience/key', async () => {
  const q = create().challenge();
  const presentation = await presentVerification(keys.publicKey, credential, h.holder, q);
  const options = {
    publicKey: keys.publicKey,
    issuer: claims.issuer,
    audience: q.audience,
    challenge: q,
    presentation,
    clock: () => NOW,
  };
  assert.equal((await verifyVerification(options)).valid, true);
  for (const change of [
    {issuer: 'wrong-issuer'},
    {audience: 'https://other.example'},
    {publicKey: (await issuerKeys()).publicKey},
    {
      challenge: {
        ...q,
        nonce: q.nonce.startsWith('A') ? 'B' + q.nonce.slice(1) : 'A' + q.nonce.slice(1),
      },
    },
    {challenge: {...q, id: q.id.startsWith('A') ? 'B' + q.id.slice(1) : 'A' + q.id.slice(1)}},
    {challenge: {...q, expires_at: NOW + 61}},
    {challenge: {...q, policy: 'adult'}},
  ])
    assert.equal((await verifyVerification({...options, ...change})).valid, false);
  let calls = 0;
  assert.equal(
    (await verifyVerification({...options, clock: () => NOW + (calls++ ? 60 : 0)})).valid,
    false,
  );
  const early = {...q, issued_at: NOW - 10, expires_at: NOW + 50};
  const proof = await presentVerification(keys.publicKey, credential, h.holder, early);
  calls = 0;
  assert.equal(
    (
      await verifyVerification({
        ...options,
        challenge: early,
        presentation: proof,
        clock: () => NOW - (calls++ ? 5 : 0),
      })
    ).valid,
    false,
  );
});

test('server proof hides source/account/device/purpose and rejects reuse', async () => {
  const v = create();
  const p = await presentVerification(keys.publicKey, credential, h.holder, v.challenge());
  const result = await v.verify(JSON.parse(JSON.stringify(p)));
  assert.equal(result.valid, true);
  for (const field of [
    'source_result_id',
    'account_id',
    'device_id',
    'source_purpose',
    'age_over_18',
  ])
    assert.equal(Object.hasOwn(result.disclosed, field), false);
  assert.equal(result.assurance, 'server-decision');
  assert.equal((await v.verify(p)).valid, false);
});

test('wrong holder, issuer, key or modified proof is rejected', async () => {
  const foreign = await prepareHolder();
  const v = create();
  await assert.rejects(
    presentVerification(keys.publicKey, credential, foreign.holder, v.challenge()),
  );
  const wrong = create({issuer: 'wrong-issuer'});
  const p = await presentVerification(keys.publicKey, credential, h.holder, wrong.challenge());
  assert.equal((await wrong.verify(p)).valid, false);
  const good = await presentVerification(keys.publicKey, credential, h.holder, v.challenge());
  assert.equal((await v.verify({...good, proof: 'A' + good.proof.slice(1)})).valid, false);
  assert.equal((await v.verify(good)).valid, true);
  await assert.rejects(
    presentVerification((await issuerKeys()).publicKey, credential, h.holder, v.challenge()),
  );
});

test('synthetic profile, arbitrary age claims and invalid lifetimes cannot be substituted', async () => {
  const demo = await issueBbs(keys, h.offer, demoClaims('adult', NOW));
  await assert.rejects(presentVerification(keys.publicKey, demo, h.holder, create().challenge()));
  for (const patch of [
    {assurance: 'synthetic-demo'},
    {age_over_18: true},
    {valid_until: NOW + 70},
    {valid_from: NOW + 1},
  ])
    await assert.rejects(issueVerification(keys, h.offer, {...claims, ...patch}));
});

test('nonce substitution and expiry during crypto are rejected', async () => {
  let time = NOW;
  const v = create({clock: () => time});
  const q = v.challenge();
  const wrong = await presentVerification(keys.publicKey, credential, h.holder, {
    ...q,
    nonce: 'A'.repeat(43),
  });
  assert.equal((await v.verify(wrong)).valid, false);
  const p = await presentVerification(keys.publicKey, credential, h.holder, q);
  const pending = v.verify(p);
  time += 60;
  assert.equal((await pending).valid, false);
});

test('pairwise pseudonyms remain scoped and three-way replay has one winner', async () => {
  const a = create(),
    b = create({audience: 'https://b.example'});
  const p1 = await presentVerification(keys.publicKey, credential, h.holder, a.challenge());
  const p2 = await presentVerification(keys.publicKey, credential, h.holder, a.challenge());
  const p3 = await presentVerification(keys.publicKey, credential, h.holder, b.challenge());
  assert.equal(p1.pseudonym, p2.pseudonym);
  assert.notEqual(p1.pseudonym, p3.pseudonym);
  assert.notEqual(p1.proof, p2.proof);
  assert.equal(
    (await Promise.all([a.verify(p1), a.verify(p1), a.verify(p1)])).filter((r) => r.valid).length,
    1,
  );
});

test('keygen preserves existing key; native pipe worker produces a verifiable credential', async () => {
  const root = fileURLToPath(new URL('../', import.meta.url));
  const dir = mkdtempSync(join(tmpdir(), 'vericlue-credentials-'));
  try {
    const path = join(dir, 'bbs.json');
    const run = (script, args = [], input = '') =>
      spawnSync(process.execPath, [join(root, script), ...args], {
        input,
        encoding: 'utf8',
        timeout: 15000,
      });
    assert.equal(run('keygen.mjs', ['--out', path]).status, 0);
    const original = readFileSync(path);
    const publicPath = join(dir, 'public.json');
    assert.equal(run('export-public-key.mjs', ['--key-file', path, '--out', publicPath]).status, 0);
    const publicFile = readFileSync(publicPath);
    const pin = JSON.parse(publicFile);
    assert.deepEqual(Object.keys(pin).sort(), ['algorithm', 'key_id', 'public_key']);
    assert.equal(pin.public_key, JSON.parse(original).public_key);
    assert.notEqual(
      run('export-public-key.mjs', ['--key-file', path, '--out', publicPath]).status,
      0,
    );
    assert.deepEqual(readFileSync(publicPath), publicFile);
    assert.equal(run('keygen.mjs', ['--out', path]).status, 0);
    assert.deepEqual(readFileSync(path), original);
    const issued = run(
      'issuer-worker.mjs',
      ['--key-file', path],
      JSON.stringify({commitment: h.offer.commitment, claims}),
    );
    assert.equal(issued.status, 0);
    const c = JSON.parse(issued.stdout);
    const publicKey = new Uint8Array(Buffer.from(JSON.parse(original).public_key, 'base64url'));
    const v = create({publicKey});
    assert.equal(
      (await v.verify(await presentVerification(publicKey, c, h.holder, v.challenge()))).valid,
      true,
    );
    for (const input of [
      '{',
      'A'.repeat(5000),
      JSON.stringify({
        commitment: h.offer.commitment,
        claims: {...claims, assurance: 'synthetic-demo'},
      }),
    ]) {
      const bad = run('issuer-worker.mjs', ['--key-file', path], input);
      assert.notEqual(bad.status, 0);
      assert.equal(bad.stdout, '');
      assert.equal(bad.stderr, '');
      const rejected = run('verifier-worker.mjs', [], input);
      assert.notEqual(rejected.status, 0);
      assert.equal(rejected.stdout, '');
      assert.equal(rejected.stderr, '');
    }
  } finally {
    assert.ok(
      resolve(dir).startsWith(resolve(tmpdir()) + sep + 'vericlue-credentials-'),
      'Unsafe test cleanup',
    );
    rmSync(dir, {recursive: true, force: true});
  }
});
