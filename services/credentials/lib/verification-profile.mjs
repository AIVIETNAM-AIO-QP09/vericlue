// Shared wire encoding for Node issuer/verifier and the browser holder. No IO or Node APIs.
export const encoded = (value) => new TextEncoder().encode(JSON.stringify(value));
export const VERIFICATION_PROTOCOL = 'vericlue-private-verification-v1';
export const VERIFICATION_HEADER = encoded([VERIFICATION_PROTOCOL, 'bbs-nym', 'server-decision']);
export const NAMES = Object.freeze([
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
export const REVEAL = Object.freeze([0, 1, 2, 3, 4, 5, 6]);
export const messages = (claims) => NAMES.map((name) => encoded([name, claims[name]]));
export const context = (q) =>
  encoded([VERIFICATION_PROTOCOL, q.audience, q.id, q.nonce, q.policy, q.issued_at, q.expires_at]);
export const validity = (c) =>
  c.valid_from % 10 === 0 &&
  c.valid_until % 10 === 0 &&
  c.valid_until > c.valid_from &&
  c.valid_until - c.valid_from <= 60;
