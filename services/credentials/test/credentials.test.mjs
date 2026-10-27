import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {HEADER, issuerKeys, issueBbs, nym, prepareHolder, presentBbs, suite} from '../lib/bbs.mjs';
import {runDemo} from '../lib/demo.mjs';
import {check} from '../lib/contract.mjs';
import {
  b64,
  bytes,
  context,
  demoClaims,
  indexesFor,
  messages,
  MAX_PENDING,
  PRIVATE_FIELDS,
  unb64,
} from '../lib/profile.mjs';
import {issueToken, presentToken, tokenKeys, visibleTokenClaims} from '../lib/tokens.mjs';
import {Verifier} from '../lib/verifier.mjs';

const NOW = Date.parse('2026-10-27T00:00:00Z') / 1000;
const wire = (value) => JSON.parse(JSON.stringify(value));
const keys = await issuerKeys();
const tokenIssuer = tokenKeys();
const tokenHolder = tokenKeys();
const prepared = await prepareHolder();
const adult = await issueBbs(keys, wire(prepared.offer), demoClaims('adult', NOW));
const minor = await issueBbs(keys, wire(prepared.offer), demoClaims('minor', NOW));
const anotherHolder = await prepareHolder();

function verifier(options = {}) {
  return new Verifier({
    audience: 'https://a.example',
    bbsPublicKey: keys.publicKey,
    tokenPublicKey: tokenIssuer.publicKey,
    clock: () => NOW,
    ...options,
  });
}

async function packet(v, {credential = adult, challenge = v.challenge('bbs-nym')} = {}) {
  return wire(await presentBbs(keys.publicKey, wire(credential), prepared.holder, wire(challenge)));
}

test('public upstream pseudonym vector verifies; modified context does not', async () => {
  const vector = JSON.parse(
    readFileSync(
      new URL('../../../packages/contracts/test-vectors/bbs-nym-public-v1.json', import.meta.url),
      'utf8',
    ),
  );
  const fields = Object.fromEntries(
    ['PK', 'header', 'ph', 'context_id', 'pseudonym', 'proof'].map((name) => [
      name,
      new Uint8Array(Buffer.from(vector[name], 'hex')),
    ]),
  );
  const params = {
    ...fields,
    L: vector.L,
    disclosed_indexes: vector.disclosed_indexes,
    disclosed_committed_indexes: vector.disclosed_committed_indexes,
    disclosed_messages: vector.disclosed_messages.map(
      (hex) => new Uint8Array(Buffer.from(hex, 'hex')),
    ),
    disclosed_committed_messages: vector.disclosed_committed_messages.map(
      (hex) => new Uint8Array(Buffer.from(hex, 'hex')),
    ),
    ciphersuite: suite,
  };
  assert.equal(await nym.ProofVerifyWithPseudonym(params), true);
  const context_id = fields.context_id.slice();
  context_id[0] ^= 1;
  assert.equal(await nym.ProofVerifyWithPseudonym({...params, context_id}), false);
});

test('offer exposes a commitment only; issuer never receives holder secrets', () => {
  assert.deepEqual(Object.keys(wire(prepared.offer)), ['commitment']);
  assert.equal(unb64(prepared.offer.commitment).length, 176);
  assert.equal(Object.hasOwn(adult, 'holder'), false);
  assert.equal(Object.hasOwn(adult, 'proverNym'), false);
});

test('BBS exchange serializes across roles and reveals no raw personal fields', async () => {
  const v = verifier();
  const p = await packet(v);
  check('BbsPresentation', p);
  const result = await v.verify(wire(p));
  assert.equal(result.valid, true);
  assert.equal(result.assurance, 'synthetic-demo');
  for (const name of PRIVATE_FIELDS) {
    assert.equal(Object.hasOwn(result.disclosed, name), false);
    assert.equal(JSON.stringify(p).includes(adult.claims[name]), false);
  }
  assert.equal(Object.hasOwn(p, 'signature'), false);
  assert.equal(Object.hasOwn(p, 'signer_entropy'), false);
  assert.equal(Object.hasOwn(p, 'publicKey'), false);
});

test('same credential: randomized proofs, stable within-service pseudonym, distinct across services', async () => {
  const a = verifier();
  const b = verifier({audience: 'https://b.example'});
  const p1 = await packet(a);
  const p2 = await packet(a);
  const p3 = await packet(b);
  assert.notEqual(p1.proof, p2.proof);
  assert.equal(p1.pseudonym, p2.pseudonym);
  assert.notEqual(p1.pseudonym, p3.pseudonym);
  assert.equal((await a.verify(p1)).valid, true);
  assert.equal((await a.verify(p2)).valid, true);
  assert.equal((await b.verify(p3)).valid, true);
});

test('replay is rejected after successful use', async () => {
  const v = verifier();
  const p = await packet(v);
  assert.equal((await v.verify(p)).valid, true);
  assert.equal((await v.verify(wire(p))).valid, false);
});

test('three concurrent copies of one proof yield exactly one success', async () => {
  const v = verifier();
  const p = await packet(v);
  const results = await Promise.all([v.verify(wire(p)), v.verify(wire(p)), v.verify(wire(p))]);
  assert.equal(results.filter((result) => result.valid).length, 1);
});

for (const changed of ['proof', 'pseudonym', 'disclosed', 'challenge_id']) {
  test(`modified ${changed} is rejected without consuming a valid challenge`, async () => {
    const v = verifier();
    const original = await packet(v);
    const bad = wire(original);
    if (changed === 'disclosed') {
      bad.disclosed.verified = false;
    } else {
      const value = bad[changed];
      bad[changed] = `${value[0] === 'A' ? 'B' : 'A'}${value.slice(1)}`;
    }
    assert.equal((await v.verify(bad)).valid, false);
    assert.equal((await v.verify(original)).valid, true);
  });
}

for (const field of ['audience', 'nonce', 'policy', 'expires_at', 'issued_at']) {
  test(`holder cannot override verifier-owned ${field}`, async () => {
    const v = verifier();
    const challenge = v.challenge('bbs-nym');
    const modified = wire(challenge);
    if (field === 'audience') modified[field] = 'https://evil.example';
    else if (field === 'nonce')
      modified[field] = `${modified[field][0] === 'A' ? 'B' : 'A'}${modified[field].slice(1)}`;
    else if (field === 'policy') modified[field] = 'verified';
    else modified[field] += 1;
    const p = await packet(v, {challenge: modified});
    assert.equal((await v.verify(p)).valid, false);
    assert.equal((await v.verify(await packet(v, {challenge}))).valid, true);
  });
}

test('cross-service replay and proof transplanted onto another challenge are rejected', async () => {
  const a = verifier();
  const b = verifier({audience: 'https://b.example'});
  const p = await packet(a);
  assert.equal((await b.verify(p)).valid, false);
  const other = a.challenge('bbs-nym');
  assert.equal((await a.verify({...p, challenge_id: other.id})).valid, false);
});

test('wrong trusted issuer key is rejected; packet cannot supply an alternative key', async () => {
  const v = verifier();
  const other = await issuerKeys();
  const p = await packet(v);
  const wrong = verifier({bbsPublicKey: other.publicKey});
  const q = wrong.challenge('bbs-nym');
  const proof = await packet(v, {challenge: q});
  assert.equal((await wrong.verify(proof)).valid, false);
  assert.equal(
    (await v.verify({...p, publicKey: Buffer.from(keys.publicKey).toString('base64url')})).valid,
    false,
  );
});

test('stolen issuer credential without holder secrets cannot produce a proof', async () => {
  const v = verifier();
  await assert.rejects(
    presentBbs(keys.publicKey, wire(adult), anotherHolder.holder, v.challenge('bbs-nym')),
  );
  await assert.rejects(presentBbs(keys.publicKey, wire(adult), {}, v.challenge('bbs-nym')));
});

test('bypassing holder SDK checks still cannot forge a proof with foreign secrets', async () => {
  const v = verifier();
  const challenge = v.challenge('bbs-nym');
  const original = await packet(v, {challenge});
  const foreign = anotherHolder.holder;
  const {proof, pseudonym} = await nym.ProofGenWithPseudonym({
    PK: keys.publicKey,
    signature: unb64(adult.signature, 80),
    header: HEADER,
    ph: context(challenge),
    messages: messages(adult.claims),
    disclosed_indexes: indexesFor(challenge.policy),
    committed_messages: [foreign.holderSecret],
    disclosed_committed_indexes: [],
    nym_secret: suite.Fr.add(foreign.proverNym, BigInt(`0x${adult.signer_entropy}`)),
    context_id: bytes(challenge.audience),
    secret_prover_blind: foreign.blinding,
    ciphersuite: suite,
  });
  assert.equal(
    (await v.verify({...original, proof: b64(proof), pseudonym: b64(pseudonym)})).valid,
    false,
  );
  assert.equal((await v.verify(original)).valid, true);
});

for (const name of ['holderSecret', 'proverNym', 'blinding']) {
  test(`each holder-side ${name} is cryptographically bound`, async () => {
    const v = verifier();
    const wrong = {...prepared.holder, [name]: anotherHolder.holder[name]};
    await assert.rejects(presentBbs(keys.publicKey, wire(adult), wrong, v.challenge('bbs-nym')));
  });
}

test('edited credential attributes or issuer entropy cannot be used', async () => {
  const v = verifier();
  await assert.rejects(
    presentBbs(
      keys.publicKey,
      {
        ...wire(minor),
        claims: {...minor.claims, age_over_18: true},
      },
      prepared.holder,
      v.challenge('bbs-nym'),
    ),
  );
  await assert.rejects(
    presentBbs(
      keys.publicKey,
      {
        ...wire(adult),
        signer_entropy: '0'.repeat(64),
      },
      prepared.holder,
      v.challenge('bbs-nym'),
    ),
  );
});

test('minor cannot meet adult policy but can prove synthetic verification only', async () => {
  const v = verifier();
  assert.equal((await v.verify(await packet(v, {credential: minor}))).valid, false);
  const challenge = v.challenge('bbs-nym', 'verified');
  const p = await packet(v, {credential: minor, challenge});
  assert.equal(Object.hasOwn(p.disclosed, 'age_over_18'), false);
  assert.equal((await v.verify(p)).valid, true);
});

test('challenge expiry and credential expiry are enforced separately', async () => {
  let time = NOW;
  const v = verifier({clock: () => time});
  const p = await packet(v);
  time += 60;
  assert.equal((await v.verify(p)).valid, false);
  time = adult.claims.valid_until;
  const expired = await packet(v);
  assert.equal((await v.verify(expired)).valid, false);
});

test('expiry during verification is rejected; no valid result escapes', async () => {
  let time = NOW;
  const v = verifier({clock: () => time});
  const p = await packet(v);
  const pending = v.verify(p);
  time += 60;
  assert.equal((await pending).valid, false);
});

test('credential expiry during crypto is rejected even if challenge is still live', async () => {
  let time = adult.claims.valid_until - 1;
  const v = verifier({clock: () => time});
  const p = await packet(v);
  const pending = v.verify(p);
  time += 2;
  assert.equal((await pending).valid, false);
});

test('a backwards verifier clock cannot make a challenge valid before issuance', async () => {
  let time = NOW;
  const v = verifier({clock: () => time});
  const p = await packet(v);
  time -= 1;
  assert.equal((await v.verify(p)).valid, false);
});

test('restarting verifier loses outstanding challenges and rejects old proofs', async () => {
  const v = verifier();
  const p = await packet(v);
  assert.equal((await verifier().verify(p)).valid, false);
});

test('challenge state is bounded and expired slots are recovered', () => {
  let time = NOW;
  const v = verifier({clock: () => time});
  for (let i = 0; i < MAX_PENDING; i++) v.challenge('bbs-nym');
  assert.throws(() => v.challenge('bbs-nym'), /capacity/);
  time += 60;
  assert.doesNotThrow(() => v.challenge('bbs-nym'));
});

for (const input of [
  null,
  [],
  {},
  {format: 'bbs-nym'},
  {format: 'none'},
  {format: 'bbs-nym', proof: 'x'.repeat(50000)},
]) {
  test(`malformed presentation is rejected (${JSON.stringify(input).slice(0, 45)})`, async () => {
    assert.equal((await verifier().verify(input)).valid, false);
  });
}

test('extra private claims, padding and wrong proof length are rejected', async () => {
  const v = verifier();
  const p = await packet(v);
  assert.equal(
    (await v.verify({...p, disclosed: {...p.disclosed, id_number: 'DEMO-ADULT'}})).valid,
    false,
  );
  assert.equal((await v.verify({...p, proof: p.proof + '='})).valid, false);
  assert.equal((await v.verify({...p, proof: p.proof + 'AAAA'})).valid, false);
  assert.equal((await v.verify(p)).valid, true);
});

test('unsafe or ambiguous verifier audiences are rejected', () => {
  for (const audience of [
    'http://a.example',
    'https://a.example/',
    'https://a.example/path',
    'https://u:p@a.example',
    'https://A.EXAMPLE',
  ]) {
    assert.throws(() => verifier({audience}));
  }
});

test('issuer rejects malformed commitments, unknown fields and real-data personas', async () => {
  await assert.rejects(issueBbs(keys, {commitment: 'A'.repeat(235)}, demoClaims('adult', NOW)));
  await assert.rejects(
    issueBbs(keys, {...prepared.offer, holderSecret: 'bad'}, demoClaims('adult', NOW)),
  );
  assert.throws(() => demoClaims('real-user', NOW));
  const real = {...adult.claims, assurance: 'real'};
  await assert.rejects(issueBbs(keys, prepared.offer, real));
  assert.equal(Buffer.from(HEADER).toString().includes('synthetic-demo'), true);
});

for (const format of ['jwt-pop', 'sd-jwt-kb']) {
  test(`${format}: verifies with holder key, rejects replay/tamper/wrong holder`, async () => {
    const v = verifier();
    const c = issueToken(tokenIssuer, tokenHolder.publicKey, demoClaims('adult', NOW), format);
    const q = v.challenge(format);
    const p = wire(presentToken(wire(c), tokenHolder.privateKey, wire(q)));
    const wrong = presentToken(wire(c), tokenKeys().privateKey, q);
    assert.equal((await v.verify(wrong)).valid, false);
    const changed = {...p, token: `${p.token[0] === 'A' ? 'B' : 'A'}${p.token.slice(1)}`};
    assert.equal((await v.verify(changed)).valid, false);
    assert.equal((await v.verify(p)).valid, true);
    assert.equal((await v.verify(p)).valid, false);
  });

  test(`${format}: wrong issuer, foreign nonce, expired and minor credentials are rejected`, async () => {
    let time = NOW;
    const v = verifier({clock: () => time});
    const q = v.challenge(format);
    const good = issueToken(tokenIssuer, tokenHolder.publicKey, demoClaims('adult', NOW), format);
    const wrongIssuer = issueToken(
      tokenKeys(),
      tokenHolder.publicKey,
      demoClaims('adult', NOW),
      format,
    );
    assert.equal(
      (await v.verify(presentToken(wrongIssuer, tokenHolder.privateKey, q))).valid,
      false,
    );
    assert.equal(
      (
        await v.verify(
          presentToken(good, tokenHolder.privateKey, {...q, audience: 'https://evil.example'}),
        )
      ).valid,
      false,
    );
    const young = issueToken(tokenIssuer, tokenHolder.publicKey, demoClaims('minor', NOW), format);
    assert.equal((await v.verify(presentToken(young, tokenHolder.privateKey, q))).valid, false);
    time += 600;
    const expired = v.challenge(format);
    assert.equal(
      (await v.verify(presentToken(good, tokenHolder.privateKey, expired))).valid,
      false,
    );
  });

  test(`${format}: exposes expected data and a stable issuer token across services`, async () => {
    const a = verifier();
    const b = verifier({audience: 'https://b.example'});
    const c = issueToken(tokenIssuer, tokenHolder.publicKey, demoClaims('adult', NOW), format);
    const p1 = presentToken(c, tokenHolder.privateKey, a.challenge(format));
    const p2 = presentToken(c, tokenHolder.privateKey, b.challenge(format));
    const visible = visibleTokenClaims(p1);
    for (const field of PRIVATE_FIELDS)
      assert.equal(Object.hasOwn(visible, field), format === 'jwt-pop');
    const r1 = await a.verify(p1);
    const r2 = await b.verify(p2);
    assert.equal(r1.valid && r2.valid, true);
    assert.equal(r1.linkable_artifact, r2.linkable_artifact);
  });
}

test('SD-JWT disclosure mutation, duplicate and removal are rejected', async () => {
  const v = verifier();
  const c = issueToken(tokenIssuer, tokenHolder.publicKey, demoClaims('adult', NOW), 'sd-jwt-kb');
  const q = v.challenge('sd-jwt-kb');
  const p = presentToken(c, tokenHolder.privateKey, q);
  const parts = p.token.split('~');
  const duplicate = [...parts];
  duplicate[2] = duplicate[1];
  assert.equal((await v.verify({...p, token: duplicate.join('~')})).valid, false);
  const removed = [...parts];
  removed.splice(1, 1);
  assert.equal((await v.verify({...p, token: removed.join('~')})).valid, false);
  assert.equal((await v.verify(p)).valid, true);
});

test('a malicious legitimate holder cannot change an SD-JWT claim even with a fresh valid KB-JWT', async () => {
  const v = verifier();
  const c = issueToken(tokenIssuer, tokenHolder.publicKey, demoClaims('minor', NOW), 'sd-jwt-kb');
  const challenge = v.challenge('sd-jwt-kb');
  const edited = wire(c);
  edited.disclosures = edited.disclosures.map((value) => {
    const tuple = JSON.parse(Buffer.from(value, 'base64url').toString('utf8'));
    if (tuple[1] === 'age_over_18') tuple[2] = true;
    return b64(Buffer.from(JSON.stringify(tuple)));
  });
  const proof = presentToken(edited, tokenHolder.privateKey, challenge);
  assert.equal((await v.verify(proof)).valid, false);
});

test('duplicate SD-JWT claims are rejected even with valid digests and a freshly signed binding', async () => {
  const v = verifier();
  const c = issueToken(tokenIssuer, tokenHolder.publicKey, demoClaims('adult', NOW), 'sd-jwt-kb');
  const age = c.disclosures.find(
    (value) => JSON.parse(Buffer.from(value, 'base64url').toString('utf8'))[1] === 'age_over_18',
  );
  const edited = wire(c);
  edited.disclosures = edited.disclosures.map((value) =>
    JSON.parse(Buffer.from(value, 'base64url').toString('utf8'))[1] === 'verified' ? age : value,
  );
  const proof = presentToken(edited, tokenHolder.privateKey, v.challenge('sd-jwt-kb'));
  assert.equal((await v.verify(proof)).valid, false);
});

test('demo reports actual crypto measurements with no secrets or raw persona data', async () => {
  const report = await runDemo({runs: 2, clock: () => NOW});
  assert.equal(report.assurance, 'synthetic-demo');
  assert.deepEqual(
    report.comparison.map((row) => row.personal_fields_visible.length),
    [3, 0, 0],
  );
  for (const row of report.comparison) {
    assert.equal(row.samples, 2);
    assert.equal(row.cryptographic_verifications, 3);
    assert.equal(row.replay_rejections, 3);
    assert.equal(row.generate_ms.length, 2);
    assert.equal(row.verify_ms.length, 2);
    assert.ok(row.presentation_median_bytes > 0);
  }
  const text = JSON.stringify(report);
  for (const forbidden of ['secretKey', 'holderSecret', 'DEMO-ADULT', 'Demo Adult', '2000-01-01']) {
    assert.equal(text.includes(forbidden), false);
  }
  await assert.rejects(runDemo({runs: 0}));
});
