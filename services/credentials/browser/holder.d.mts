/** Runtime validation uses packages/contracts/schemas/{credential,result}.schema.json. */
export interface HolderExpectedContext {
  issuer: string;
  audience: string;
  session_id: string;
  nonce: string;
  purpose: 'reauth' | 'recovery';
  account_id: string;
  device_id: string;
}

export interface SignedResult {
  algorithm: 'Ed25519';
  key_id: string;
  payload: string;
  signature: string;
}
export interface SigningKey {
  algorithm: 'Ed25519';
  key_id: string;
  public_key_spki: string;
}
export interface CredentialKey {
  algorithm: 'BBS-BLS12-381-SHA-256-NYM';
  key_id: string;
  public_key: string;
}
export interface CredentialAuthorization {
  algorithm: 'ES256-DER';
  message: string;
  expires_at: number;
}
export interface CredentialOfferRequest {
  commitment: string;
  consent: true;
}
export interface CredentialIssueRequest extends CredentialOfferRequest {
  device_signature: string;
}
export interface VerificationDisclosed {
  protocol: 'vericlue-private-verification-v1';
  issuer: string;
  assurance: 'server-decision';
  verification_completed: true;
  valid_from: number;
  valid_until: number;
  policy_version: 'vericlue-session-result-v1';
}
export interface VerificationCredential {
  key_id: string;
  signature: string;
  signer_entropy: string;
  claims: VerificationDisclosed & {
    source_result_id: string;
    account_id: string;
    device_id: string;
    source_purpose: 'reauth' | 'recovery';
  };
}
export interface VerificationChallenge {
  id: string;
  nonce: string;
  audience: string;
  format: 'bbs-nym';
  policy: 'verified';
  issued_at: number;
  expires_at: number;
}
export interface VerificationPresentation {
  protocol: 'vericlue-private-verification-v1';
  challenge_id: string;
  disclosed: VerificationDisclosed;
  proof: string;
  pseudonym: string;
}
export interface WalletMetadata {
  state: 'ready' | 'prepared' | 'authorized' | 'issued' | 'closed';
  expires_at: number;
}
/** Sign exact bytes using the already enrolled P-256 device key; return ASN.1 DER. */
export type DeviceSigner = (message: Uint8Array) => Promise<Uint8Array>;
export interface VerificationWallet {
  metadata(): WalletMetadata;
  prepare(options: {consent: true}): Promise<CredentialOfferRequest>;
  authorize(
    authorization: CredentialAuthorization,
    signDevice: DeviceSigner,
  ): Promise<CredentialIssueRequest>;
  accept(credential: VerificationCredential): Promise<WalletMetadata>;
  present(
    challenge: VerificationChallenge,
    options: {audience: string; consent: true},
  ): Promise<VerificationPresentation>;
  destroy(): void;
}
export class HolderError extends Error {
  readonly code: string;
  constructor(code: string);
}
export function webCryptoP256Signer(key: CryptoKey): DeviceSigner;
export function createVerificationWallet(options: {
  result: SignedResult;
  resultKey: SigningKey;
  credentialKey: CredentialKey;
  expected: HolderExpectedContext;
  /** Unix seconds; omit in applications. Injectable for deterministic conformance tests. */
  clock?: () => number;
}): Promise<VerificationWallet>;
