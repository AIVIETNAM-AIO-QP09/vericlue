import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {randomBytes} from 'node:crypto';
import {generateKeyPair} from '@digitalbazaar/bbs-signatures';
import {check} from './contract.mjs';
import {
  CLAIM_NAMES,
  PROTOCOL,
  allowed,
  b64,
  bytes,
  context,
  disclosed,
  encoded,
  indexesFor,
  messages,
  origin,
  unb64,
} from './profile.mjs';

// Upstream 3.1.0 packages these draft APIs but does not expose their subpaths.
// Pin the package/lockfile; conformance tests guard this deliberate lab-only adapter.
const root = pathToFileURL(createRequire(import.meta.url).resolve('@digitalbazaar/bbs-signatures'));
export const nym = await import(new URL('bbs/pseudonym/interface.js', root));
export const suite = (await import(new URL('bbs/ciphersuites.js', root))).getCiphersuite(
  'BLS12-381-SHA-256',
);
export const HEADER = encoded([PROTOCOL, 'bbs-nym', 'synthetic-demo']);
const scalar = (value) => BigInt(`0x${Buffer.from(value).toString('hex')}`);
const scalarHex = (value) => value.toString(16).padStart(64, '0');

function randomScalar() {
  for (;;) {
    const value = scalar(randomBytes(32));
    if (value > 0n && value < suite.r) {
      return value;
    }
  }
}

export async function issuerKeys() {
  return generateKeyPair({ciphersuite: suite.name});
}

export async function prepareHolder() {
  const holderSecret = new Uint8Array(randomBytes(32));
  const proverNym = randomScalar();
  const {commitment_with_proof, secret_prover_blind} = await nym.NymCommit({
    prover_nym: proverNym,
    committed_messages: [holderSecret],
    ciphersuite: suite,
  });
  return {
    offer: check('Offer', {commitment: b64(commitment_with_proof)}),
    // These values never cross the holder -> issuer boundary or enter presentations.
    holder: {holderSecret, proverNym, blinding: secret_prover_blind},
  };
}

export async function issueBbs(keys, offer, claims) {
  check('Offer', offer);
  check('Claims', claims);
  const signerEntropy = randomScalar();
  const signature = await nym.BlindSignWithNym({
    SK: scalar(keys.secretKey),
    PK: keys.publicKey,
    commitment_with_proof: unb64(offer.commitment, 176),
    header: HEADER,
    messages: messages(claims),
    signer_nym_entropy: signerEntropy,
    ciphersuite: suite,
  });
  return check('BbsCredential', {
    claims: structuredClone(claims),
    signature: b64(signature),
    signer_entropy: scalarHex(signerEntropy),
  });
}

export async function presentBbs(publicKey, credential, holder, challenge) {
  check('BbsCredential', credential);
  check('Challenge', challenge);
  origin(challenge.audience);
  if (challenge.format !== 'bbs-nym') {
    throw new Error('Wrong presentation format');
  }
  const signerEntropy = BigInt(`0x${credential.signer_entropy}`);
  if (signerEntropy <= 0n || signerEntropy >= suite.r) {
    throw new Error('Invalid signer entropy');
  }
  const allMessages = messages(credential.claims);
  const signature = unb64(credential.signature, 80);
  const {verified, nym_secret} = await nym.BlindVerifyWithNym({
    PK: publicKey,
    signature,
    header: HEADER,
    messages: allMessages,
    committed_messages: [holder.holderSecret],
    prover_nym: holder.proverNym,
    signer_nym_entropy: signerEntropy,
    secret_prover_blind: holder.blinding,
    ciphersuite: suite,
  });
  if (!verified || nym_secret === 0n) {
    throw new Error('Credential is not bound to this holder');
  }
  const {proof, pseudonym} = await nym.ProofGenWithPseudonym({
    PK: publicKey,
    signature,
    header: HEADER,
    ph: context(challenge),
    messages: allMessages,
    disclosed_indexes: indexesFor(challenge.policy),
    committed_messages: [holder.holderSecret],
    disclosed_committed_indexes: [],
    nym_secret,
    context_id: bytes(challenge.audience),
    secret_prover_blind: holder.blinding,
    ciphersuite: suite,
  });
  return check('BbsPresentation', {
    format: 'bbs-nym',
    challenge_id: challenge.id,
    disclosed: disclosed(credential.claims, challenge.policy),
    proof: b64(proof),
    pseudonym: b64(pseudonym),
  });
}

export async function verifyBbs(publicKey, presentation, challenge, now) {
  check('BbsPresentation', presentation);
  const indexes = indexesFor(challenge.policy);
  if (
    Object.keys(presentation.disclosed).length !== indexes.length ||
    !allowed(presentation.disclosed, challenge, now)
  ) {
    return false;
  }
  // Exactly one hidden holder message, blind factor and nym; never accept arbitrary generators.
  const expectedProofSize = 272 + 32 * (CLAIM_NAMES.length + 3 - indexes.length);
  const valid = await nym.ProofVerifyWithPseudonym({
    PK: publicKey,
    proof: unb64(presentation.proof, expectedProofSize),
    pseudonym: unb64(presentation.pseudonym, 48),
    context_id: bytes(challenge.audience),
    header: HEADER,
    ph: context(challenge),
    L: CLAIM_NAMES.length,
    disclosed_messages: indexes.map((i) =>
      encoded([CLAIM_NAMES[i], presentation.disclosed[CLAIM_NAMES[i]]]),
    ),
    disclosed_indexes: indexes,
    disclosed_committed_messages: [],
    disclosed_committed_indexes: [],
    ciphersuite: suite,
  });
  return valid === true;
}
