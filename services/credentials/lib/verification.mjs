import {createHash, randomBytes} from 'node:crypto';
import {nym, suite} from './bbs.mjs';
import {check, checkCredential} from './contract.mjs';
import {
  b64,
  bytes,
  encoded,
  origin,
  randomId,
  unb64,
  MAX_PENDING,
  CHALLENGE_TTL,
} from './profile.mjs';

export const VERIFICATION_PROTOCOL = 'vericlue-private-verification-v1';
export const VERIFICATION_HEADER = encoded([VERIFICATION_PROTOCOL, 'bbs-nym', 'server-decision']);
const NAMES = Object.freeze([
  'protocol',
  'issuer',
  'assurance',
  'verification_completed',
  'valid_from',
  'valid_until',
  'policy_version',
  'source_result_id',
  'account_id',
  'device_id',
  'source_purpose',
]);
const REVEAL = Object.freeze([0, 1, 2, 3, 4, 5, 6]);
const messages = (c) => NAMES.map((n) => encoded([n, c[n]]));
const scalar = (b) => BigInt(`0x${Buffer.from(b).toString('hex')}`);
const kid = (key) => createHash('sha256').update(key).digest('hex');
const context = (q) =>
  encoded([VERIFICATION_PROTOCOL, q.audience, q.id, q.nonce, q.policy, q.issued_at, q.expires_at]);

function validity(c) {
  return (
    c.valid_from % 10 === 0 &&
    c.valid_until % 10 === 0 &&
    c.valid_until > c.valid_from &&
    c.valid_until - c.valid_from <= 60
  );
}

export async function issueVerification(keys, offer, claims) {
  check('Offer', offer);
  checkCredential('VerificationClaims', claims);
  if (!validity(claims)) throw new Error('Invalid validity');
  let entropy;
  do {
    entropy = scalar(randomBytes(32));
  } while (entropy === 0n || entropy >= suite.r);
  const signature = await nym.BlindSignWithNym({
    SK: scalar(keys.secretKey),
    PK: keys.publicKey,
    commitment_with_proof: unb64(offer.commitment, 176),
    header: VERIFICATION_HEADER,
    messages: messages(claims),
    signer_nym_entropy: entropy,
    ciphersuite: suite,
  });
  return checkCredential('VerificationCredential', {
    claims: structuredClone(claims),
    signature: b64(signature),
    signer_entropy: entropy.toString(16).padStart(64, '0'),
    key_id: kid(keys.publicKey),
  });
}

export async function presentVerification(publicKey, credential, holder, q) {
  checkCredential('VerificationCredential', credential);
  check('Challenge', q);
  origin(q.audience);
  if (
    q.format !== 'bbs-nym' ||
    q.policy !== 'verified' ||
    !validity(credential.claims) ||
    credential.key_id !== kid(publicKey)
  ) {
    throw new Error('Invalid context');
  }
  const entropy = BigInt(`0x${credential.signer_entropy}`);
  if (entropy <= 0n || entropy >= suite.r) throw new Error('Invalid entropy');
  const signature = unb64(credential.signature, 80);
  const common = {
    PK: publicKey,
    signature,
    header: VERIFICATION_HEADER,
    messages: messages(credential.claims),
    committed_messages: [holder.holderSecret],
    secret_prover_blind: holder.blinding,
    ciphersuite: suite,
  };
  const result = await nym.BlindVerifyWithNym({
    ...common,
    prover_nym: holder.proverNym,
    signer_nym_entropy: entropy,
  });
  if (!result.verified || result.nym_secret === 0n) throw new Error('Holder not bound');
  const {proof, pseudonym} = await nym.ProofGenWithPseudonym({
    ...common,
    ph: context(q),
    disclosed_indexes: REVEAL,
    disclosed_committed_indexes: [],
    nym_secret: result.nym_secret,
    context_id: bytes(q.audience),
  });
  return checkCredential('VerificationPresentation', {
    protocol: VERIFICATION_PROTOCOL,
    challenge_id: q.id,
    disclosed: Object.fromEntries(REVEAL.map((i) => [NAMES[i], credential.claims[NAMES[i]]])),
    proof: b64(proof),
    pseudonym: b64(pseudonym),
  });
}

// Stateless crypto boundary. Callers must atomically reserve/consume the persisted
// challenge; supplying a presentation's own context is never sufficient.
export async function verifyVerification({
  publicKey,
  issuer,
  audience,
  challenge: q,
  presentation,
  clock = () => Math.floor(Date.now() / 1000),
}) {
  try {
    checkCredential('VerificationChallenge', q);
    checkCredential('VerificationPresentation', presentation);
    origin(audience);
    const now = clock();
    const c = presentation.disclosed;
    if (
      publicKey.length !== 96 ||
      !/^[A-Za-z0-9:/._-]{1,200}$/.test(issuer) ||
      q.audience !== audience ||
      q.id !== presentation.challenge_id ||
      q.issued_at > now ||
      q.expires_at <= now ||
      q.expires_at - q.issued_at > CHALLENGE_TTL ||
      q.expires_at <= q.issued_at ||
      c.issuer !== issuer ||
      !validity(c) ||
      now < c.valid_from ||
      now >= c.valid_until
    )
      throw new Error('Invalid context');
    const ok = await nym.ProofVerifyWithPseudonym({
      PK: publicKey,
      header: VERIFICATION_HEADER,
      ph: context(q),
      proof: unb64(presentation.proof, 496),
      pseudonym: unb64(presentation.pseudonym, 48),
      context_id: bytes(audience),
      L: NAMES.length,
      disclosed_indexes: REVEAL,
      disclosed_messages: REVEAL.map((i) => encoded([NAMES[i], c[NAMES[i]]])),
      disclosed_committed_messages: [],
      disclosed_committed_indexes: [],
      ciphersuite: suite,
    });
    const finished = clock();
    if (
      !ok ||
      finished < Math.max(q.issued_at, c.valid_from) ||
      finished >= q.expires_at ||
      finished >= c.valid_until
    )
      throw new Error('Invalid proof');
    return checkCredential('VerificationAccepted', {
      valid: true,
      assurance: 'server-decision',
      disclosed: structuredClone(c),
      pseudonym: presentation.pseudonym,
    });
  } catch {
    return {valid: false};
  }
}

export class VerificationVerifier {
  #key;
  #issuer;
  #audience;
  #clock;
  #pending = new Map();

  constructor({publicKey, issuer, audience, clock = () => Math.floor(Date.now() / 1000)}) {
    this.#key = new Uint8Array(publicKey);
    if (
      this.#key.length !== 96 ||
      typeof issuer !== 'string' ||
      !/^[A-Za-z0-9:/._-]{1,200}$/.test(issuer)
    )
      throw new Error('Trusted issuer required');
    this.#issuer = issuer;
    this.#audience = origin(audience);
    this.#clock = clock;
  }

  challenge() {
    const now = this.#clock();
    for (const [id, e] of this.#pending) if (e.q.expires_at <= now) this.#pending.delete(id);
    if (this.#pending.size >= MAX_PENDING) throw new Error('Challenge capacity reached');
    const q = check('Challenge', {
      id: randomId(16),
      nonce: randomId(32),
      audience: this.#audience,
      format: 'bbs-nym',
      policy: 'verified',
      issued_at: now,
      expires_at: now + CHALLENGE_TTL,
    });
    this.#pending.set(q.id, {q: structuredClone(q), busy: false});
    return structuredClone(q);
  }

  async verify(presentation) {
    let entry;
    let reserved = false;
    try {
      checkCredential('VerificationPresentation', presentation);
      entry = this.#pending.get(presentation.challenge_id);
      const now = this.#clock();
      if (!entry || entry.busy || entry.q.issued_at > now || entry.q.expires_at <= now)
        throw new Error('Unavailable challenge');
      entry.busy = true;
      reserved = true;
      const result = await verifyVerification({
        publicKey: this.#key,
        issuer: this.#issuer,
        audience: this.#audience,
        challenge: entry.q,
        presentation,
        clock: this.#clock,
      });
      if (!result.valid || this.#pending.get(entry.q.id) !== entry)
        throw new Error('Invalid proof');
      this.#pending.delete(entry.q.id);
      return result;
    } catch {
      return {valid: false};
    } finally {
      if (reserved) entry.busy = false;
    }
  }
}
