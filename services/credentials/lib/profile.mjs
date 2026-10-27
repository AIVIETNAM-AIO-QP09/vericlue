import {randomBytes} from 'node:crypto';
import {check} from './contract.mjs';

export const PROTOCOL = 'vericlue-private-credential-lab-v1';
export const CLAIM_NAMES = Object.freeze([
  'protocol',
  'issuer',
  'assurance',
  'valid_from',
  'valid_until',
  'verified',
  'age_over_18',
  'full_name',
  'id_number',
  'birth_date',
  'policy_version',
]);
export const MANDATORY = Object.freeze([0, 1, 2, 3, 4, 5, 10]);
export const PRIVATE_FIELDS = Object.freeze(['full_name', 'id_number', 'birth_date']);
export const COHORT_SECONDS = 300;
export const CREDENTIAL_TTL = 600;
export const CHALLENGE_TTL = 60;
export const MAX_PENDING = 128;
export const bytes = (value) => new TextEncoder().encode(value);
export const encoded = (value) => bytes(JSON.stringify(value));
export const b64 = (value) => Buffer.from(value).toString('base64url');
export const randomId = (length) => b64(randomBytes(length));

export function unb64(text, size) {
  if (typeof text !== 'string' || !/^[A-Za-z0-9_-]+$/.test(text) || text.length > 16384) {
    throw new Error('Invalid base64url');
  }
  const value = new Uint8Array(Buffer.from(text, 'base64url'));
  if (b64(value) !== text || (size !== undefined && value.length !== size)) {
    throw new Error('Invalid base64url');
  }
  return value;
}

export function origin(value) {
  const url = new URL(value);
  if (value.length > 200 || url.protocol !== 'https:' || url.origin !== value) {
    throw new Error('Audience must be an exact HTTPS origin');
  }
  return value;
}

export function demoClaims(persona, now) {
  if (!['adult', 'minor'].includes(persona) || !Number.isSafeInteger(now) || now < 0) {
    throw new Error('Only synthetic personas are available');
  }
  const adult = persona === 'adult';
  const birth_date = adult ? '2000-01-01' : '2015-01-01';
  const today = new Date(now * 1000).toISOString().slice(0, 10);
  const eighteenth = `${Number(birth_date.slice(0, 4)) + 18}${birth_date.slice(4)}`;
  const valid_from = Math.floor(now / COHORT_SECONDS) * COHORT_SECONDS;
  return check('Claims', {
    protocol: PROTOCOL,
    issuer: 'vericlue-lab',
    assurance: 'synthetic-demo',
    valid_from,
    valid_until: valid_from + CREDENTIAL_TTL,
    verified: true,
    age_over_18: today >= eighteenth,
    full_name: adult ? 'Demo Adult' : 'Demo Minor',
    id_number: adult ? 'DEMO-ADULT' : 'DEMO-MINOR',
    birth_date,
    policy_version: 'lab-policy-v1',
  });
}

export function indexesFor(policy) {
  if (!['verified', 'adult'].includes(policy)) {
    throw new Error('Unknown policy');
  }
  return [...MANDATORY, ...(policy === 'adult' ? [6] : [])].sort((a, b) => a - b);
}

export function messages(claims) {
  return CLAIM_NAMES.map((name) => encoded([name, claims[name]]));
}

export function disclosed(claims, policy) {
  return Object.fromEntries(
    indexesFor(policy).map((i) => [CLAIM_NAMES[i], claims[CLAIM_NAMES[i]]]),
  );
}

export function context(challenge) {
  // Reconstruct from verifier-owned state; never accept a presentation's header.
  return encoded([
    PROTOCOL,
    'presentation',
    challenge.format,
    challenge.audience,
    challenge.id,
    challenge.nonce,
    challenge.policy,
    challenge.issued_at,
    challenge.expires_at,
  ]);
}

export function allowed(claims, challenge, now) {
  check('DisclosedClaims', disclosed(claims, challenge.policy));
  return (
    claims.verified === true &&
    claims.valid_from <= now &&
    now < claims.valid_until &&
    claims.valid_until - claims.valid_from === CREDENTIAL_TTL &&
    claims.valid_from % COHORT_SECONDS === 0 &&
    (challenge.policy !== 'adult' || claims.age_over_18 === true)
  );
}
