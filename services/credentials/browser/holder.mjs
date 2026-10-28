import * as validators from '#holder-validators';
import {NymCommit, BlindVerifyWithNym, ProofGenWithPseudonym} from '#bbs-nym';
import {getCiphersuite} from '#bbs-suite';
import {
  VERIFICATION_PROTOCOL,
  VERIFICATION_HEADER,
  NAMES,
  REVEAL,
  messages,
  context,
  validity,
} from '../lib/verification-profile.mjs';
import {
  bytes,
  text,
  hex,
  hash,
  canonical,
  base64,
  b64,
  decode,
  origin,
  p256Der,
} from './encoding.mjs';

const suite = getCiphersuite('BLS12-381-SHA-256');
const TOKEN = Symbol('verified holder context');
const NOW = () => Math.floor(Date.now() / 1000);

export class HolderError extends Error {
  constructor(code) {
    super(code);
    this.name = 'HolderError';
    this.code = code;
  }
}

const reject = (code = 'holder_invalid_context') => {
  throw new HolderError(code);
};

function copy(type, value) {
  const result = structuredClone(value);
  if (JSON.stringify(result).length > 8192 || !validators[type]?.(result)) reject();
  return result;
}

function current(clock) {
  const value = clock();
  if (!Number.isSafeInteger(value) || value < 0) reject('holder_invalid_clock');
  return value;
}

function consent(value) {
  if (value !== true) reject('holder_consent_required');
}

function randomScalar() {
  for (;;) {
    const value = BigInt('0x' + hex(globalThis.crypto.getRandomValues(new Uint8Array(32))));
    if (value > 0n && value < suite.r) return value;
  }
}

/** The host supplies its already enrolled key. Non-extractable does not mean hardware-backed. */
export function webCryptoP256Signer(key) {
  if (
    key?.type !== 'private' ||
    key.extractable !== false ||
    key.algorithm?.name !== 'ECDSA' ||
    key.algorithm.namedCurve !== 'P-256' ||
    !key.usages.includes('sign')
  )
    reject();
  return async (message) =>
    p256Der(
      new Uint8Array(
        await globalThis.crypto.subtle.sign({name: 'ECDSA', hash: 'SHA-256'}, key, message),
      ),
    );
}

/** Verify the server's Ed25519 result against application-owned pins/context, without IO. */
export async function createVerificationWallet({
  result,
  resultKey,
  credentialKey,
  expected,
  clock = NOW,
}) {
  try {
    if (
      !globalThis.crypto?.subtle ||
      !globalThis.crypto?.getRandomValues ||
      globalThis.isSecureContext === false
    )
      reject('holder_runtime_unavailable');
    const envelope = copy('SignedResult', result);
    const resultPin = copy('SigningKey', resultKey);
    const pin = copy('CredentialKey', credentialKey);
    const wanted = copy('HolderExpectedContext', expected);
    const spki = decode(resultPin.public_key_spki, {url: false, size: 44});
    if ((await hash(spki)) !== resultPin.key_id || envelope.key_id !== resultPin.key_id)
      reject('holder_invalid_source');
    const raw = decode(envelope.payload),
      signature = decode(envelope.signature, {size: 64});
    const publicKey = await globalThis.crypto.subtle.importKey(
      'spki',
      spki,
      {name: 'Ed25519'},
      false,
      ['verify'],
    );
    const signed = new Uint8Array([
      ...bytes('vericlue-session-result-v1\0' + envelope.key_id + '\0'),
      ...raw,
    ]);
    if (!(await globalThis.crypto.subtle.verify('Ed25519', publicKey, signature, signed)))
      reject('holder_invalid_source');
    const claims = copy('ResultClaims', JSON.parse(text(raw)));
    if (
      text(raw) !== canonical(claims) ||
      claims.status !== 'pass' ||
      !Object.keys(wanted).every((key) => claims[key] === wanted[key]) ||
      !(0 < claims.expires_at - claims.issued_at && claims.expires_at - claims.issued_at <= 60)
    )
      reject('holder_invalid_source');
    const now = current(clock);
    if (!(claims.issued_at <= now && now < claims.expires_at)) reject('holder_expired');
    const pk = decode(pin.public_key, {size: 96});
    if ((await hash(pk)) !== pin.key_id) reject('holder_invalid_source');
    const certified = {
      protocol: VERIFICATION_PROTOCOL,
      issuer: claims.issuer,
      assurance: 'server-decision',
      verification_completed: true,
      valid_from: Math.floor(claims.issued_at / 10) * 10,
      valid_until: Math.floor(claims.expires_at / 10) * 10,
      policy_version: 'vericlue-session-result-v1',
      source_result_id: claims.result_id,
      account_id: claims.account_id,
      device_id: claims.device_id,
      source_purpose: claims.purpose,
    };
    const finished = current(clock);
    if (!validity(certified) || finished < claims.issued_at || finished >= certified.valid_until)
      reject('holder_expired');
    return new Wallet(TOKEN, {claims, certified, pin, pk, clock});
  } catch (error) {
    if (error instanceof HolderError) throw error;
    reject('holder_invalid_source');
  }
}

class Wallet {
  #source;
  #claims;
  #pin;
  #pk;
  #clock;
  #holder;
  #offer;
  #credential;
  #nym;
  #phase = 'ready';
  #busy = false;
  #generation = 0;

  constructor(token, {claims, certified, pin, pk, clock}) {
    if (token !== TOKEN) reject();
    this.#source = claims;
    this.#claims = certified;
    this.#pin = pin;
    this.#pk = pk;
    this.#clock = clock;
  }

  metadata() {
    return {state: this.#phase, expires_at: this.#claims?.valid_until ?? 0};
  }

  #live(generation = this.#generation) {
    if (this.#phase === 'closed' || generation !== this.#generation) reject('holder_closed');
    const now = current(this.#clock);
    if (!(
      Math.max(this.#claims.valid_from, this.#source.issued_at) <= now &&
      now < this.#claims.valid_until
    )) {
      this.destroy();
      reject('holder_expired');
    }
    return now;
  }

  async #run(phases, operation) {
    this.#live();
    if (this.#busy) reject('holder_busy');
    if (!phases.includes(this.#phase)) reject('holder_wrong_state');
    this.#busy = true;
    const generation = this.#generation;
    const guard = () => this.#live(generation);
    try {
      return await operation(guard);
    } catch (error) {
      if (error instanceof HolderError) throw error;
      reject('holder_operation_failed');
    } finally {
      if (generation === this.#generation) this.#busy = false;
    }
  }

  async prepare({consent: approved} = {}) {
    consent(approved);
    return this.#run(['ready'], async (guard) => {
      this.#holder = {
        holderSecret: globalThis.crypto.getRandomValues(new Uint8Array(32)),
        proverNym: randomScalar(),
      };
      try {
        const {commitment_with_proof, secret_prover_blind} = await NymCommit({
          prover_nym: this.#holder.proverNym,
          committed_messages: [this.#holder.holderSecret],
          ciphersuite: suite,
        });
        guard();
        this.#holder.blinding = secret_prover_blind;
        this.#offer = b64(commitment_with_proof);
        this.#phase = 'prepared';
        return {commitment: this.#offer, consent: true};
      } catch (error) {
        this.destroy();
        throw error;
      }
    });
  }

  async authorize(authorization, signDevice) {
    return this.#run(['prepared', 'authorized'], async (guard) => {
      const auth = copy('CredentialAuthorization', authorization);
      const expected = {
        protocol: 'vericlue-credential-authorization-v1',
        session_id: this.#source.session_id,
        source_result_id: this.#source.result_id,
        account_id: this.#source.account_id,
        device_id: this.#source.device_id,
        offer_sha256: await hash(decode(this.#offer, {size: 176})),
        key_id: this.#pin.key_id,
        expires_at: this.#claims.valid_until,
        consent: true,
      };
      if (
        !validators.CredentialAuthorizationContext(expected) ||
        auth.expires_at !== expected.expires_at ||
        typeof signDevice !== 'function'
      )
        reject();
      const message = decode(auth.message, {url: false, max: 2048});
      if (text(message) !== canonical(expected)) reject();
      guard();
      const signature = await signDevice(message.slice());
      guard();
      if (
        !(signature instanceof Uint8Array) ||
        signature.length < 8 ||
        signature.length > 80 ||
        signature[0] !== 48
      )
        reject('holder_invalid_device_signature');
      this.#phase = 'authorized';
      return {commitment: this.#offer, consent: true, device_signature: base64(signature)};
    });
  }

  async accept(credential) {
    return this.#run(['authorized'], async (guard) => {
      const value = copy('VerificationCredential', credential);
      if (
        value.key_id !== this.#pin.key_id ||
        !NAMES.every((name) => value.claims[name] === this.#claims[name])
      )
        reject();
      const entropy = BigInt('0x' + value.signer_entropy);
      if (entropy <= 0n || entropy >= suite.r) reject();
      const checked = await BlindVerifyWithNym({
        PK: this.#pk,
        signature: decode(value.signature, {size: 80}),
        header: VERIFICATION_HEADER,
        messages: messages(value.claims),
        committed_messages: [this.#holder.holderSecret],
        prover_nym: this.#holder.proverNym,
        signer_nym_entropy: entropy,
        secret_prover_blind: this.#holder.blinding,
        ciphersuite: suite,
      });
      guard();
      if (!checked.verified || checked.nym_secret === 0n) reject();
      this.#nym = checked.nym_secret;
      this.#credential = value;
      this.#phase = 'issued';
      return this.metadata();
    });
  }

  async present(challenge, {audience, consent: approved} = {}) {
    consent(approved);
    return this.#run(['issued'], async (guard) => {
      const q = copy('VerificationChallenge', challenge);
      const now = guard();
      if (
        origin(audience) !== q.audience ||
        q.issued_at > now ||
        now >= q.expires_at ||
        !(0 < q.expires_at - q.issued_at && q.expires_at - q.issued_at <= 60)
      )
        reject('holder_invalid_challenge');
      decode(q.id, {size: 16});
      decode(q.nonce, {size: 32});
      const {proof, pseudonym} = await ProofGenWithPseudonym({
        PK: this.#pk,
        signature: decode(this.#credential.signature, {size: 80}),
        header: VERIFICATION_HEADER,
        ph: context(q),
        messages: messages(this.#claims),
        committed_messages: [this.#holder.holderSecret],
        disclosed_indexes: REVEAL,
        disclosed_committed_indexes: [],
        nym_secret: this.#nym,
        context_id: bytes(q.audience),
        secret_prover_blind: this.#holder.blinding,
        ciphersuite: suite,
      });
      const finished = guard();
      if (finished < q.issued_at || finished >= q.expires_at) reject('holder_invalid_challenge');
      return copy('VerificationPresentation', {
        protocol: VERIFICATION_PROTOCOL,
        challenge_id: q.id,
        disclosed: Object.fromEntries(REVEAL.map((i) => [NAMES[i], this.#claims[NAMES[i]]])),
        proof: b64(proof),
        pseudonym: b64(pseudonym),
      });
    });
  }

  destroy() {
    this.#generation++;
    this.#holder?.holderSecret.fill(0);
    if (this.#holder) {
      this.#holder.proverNym = 0n;
      this.#holder.blinding = 0n;
    }
    this.#holder = this.#credential = this.#claims = this.#source = this.#pin = this.#pk = null;
    this.#offer = this.#nym = null;
    this.#phase = 'closed';
    this.#busy = false;
  }
}
