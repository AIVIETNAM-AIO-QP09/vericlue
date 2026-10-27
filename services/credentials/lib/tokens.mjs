import {createHash, createPublicKey, generateKeyPairSync, sign, verify} from 'node:crypto';
import {check} from './contract.mjs';
import {
  CLAIM_NAMES,
  PROTOCOL,
  allowed,
  b64,
  context,
  encoded,
  indexesFor,
  randomId,
  unb64,
} from './profile.mjs';

export const digest = (value) => createHash('sha256').update(value).digest('base64url');
export const tokenKeys = () => generateKeyPairSync('ed25519');
const headerFor = (typ) => ({alg: 'EdDSA', typ});

function jsonPart(part) {
  const text = Buffer.from(unb64(part)).toString('utf8');
  const parsed = JSON.parse(text);
  // This local profile issues canonical JSON only. Reject duplicate keys and ambiguous encodings.
  if (JSON.stringify(parsed) !== text) {
    throw new Error('Noncanonical token JSON');
  }
  return parsed;
}

function signed(payload, key, typ) {
  const input = `${b64(encoded(headerFor(typ)))}.${b64(encoded(payload))}`;
  return `${input}.${b64(sign(null, Buffer.from(input), key))}`;
}

function verified(token, key, typ) {
  if (typeof token !== 'string' || token.length > 16384) {
    throw new Error('Invalid token');
  }
  const parts = token.split('.');
  if (
    parts.length !== 3 ||
    JSON.stringify(jsonPart(parts[0])) !== JSON.stringify(headerFor(typ)) ||
    !verify(null, Buffer.from(`${parts[0]}.${parts[1]}`), key, unb64(parts[2], 64))
  ) {
    throw new Error('Invalid token signature');
  }
  return jsonPart(parts[1]);
}

function holderKey(jwk) {
  if (
    !jwk ||
    Object.keys(jwk).sort().join(',') !== 'crv,kty,x' ||
    jwk.kty !== 'OKP' ||
    jwk.crv !== 'Ed25519'
  ) {
    throw new Error('Invalid holder public key');
  }
  unb64(jwk.x, 32);
  return createPublicKey({key: jwk, format: 'jwk'});
}

export function issueToken(keys, holderPublicKey, claims, format) {
  check('Claims', claims);
  if (!['sd-jwt-kb', 'jwt-pop'].includes(format)) {
    throw new Error('Invalid token format');
  }
  const cnf = {jwk: holderPublicKey.export({format: 'jwk'})};
  const base = {
    iss: 'vericlue-lab',
    iat: claims.valid_from,
    exp: claims.valid_until,
    vct: PROTOCOL,
    cnf,
  };
  if (format === 'jwt-pop') {
    return {jwt: signed({...base, claims}, keys.privateKey, 'vericlue-lab+jwt')};
  }
  const disclosures = CLAIM_NAMES.map((name) => b64(encoded([randomId(16), name, claims[name]])));
  const jwt = signed(
    {
      ...base,
      _sd_alg: 'sha-256',
      _sd: disclosures.map(digest).sort(),
    },
    keys.privateKey,
    'vericlue-lab+sd-jwt',
  );
  return {jwt, disclosures};
}

export function presentToken(credential, holderPrivateKey, challenge) {
  check('Challenge', challenge);
  const isSd = challenge.format === 'sd-jwt-kb';
  if (!isSd && challenge.format !== 'jwt-pop') {
    throw new Error('Invalid token format');
  }
  let disclosures = [];
  if (isSd) {
    const names = indexesFor(challenge.policy).map((i) => CLAIM_NAMES[i]);
    disclosures = credential.disclosures.filter((d) => names.includes(jsonPart(d)[1]));
  }
  const prefix = [credential.jwt, ...disclosures, ''].join('~');
  const hashName = isSd ? 'sd_hash' : 'token_hash';
  const binding = signed(
    {
      iat: challenge.issued_at,
      aud: challenge.audience,
      nonce: challenge.nonce,
      [hashName]: digest(prefix),
      ctx: digest(context(challenge)),
    },
    holderPrivateKey,
    isSd ? 'kb+jwt' : 'vericlue-lab-pop+jwt',
  );
  return check('TokenPresentation', {
    format: challenge.format,
    challenge_id: challenge.id,
    token: prefix + binding,
  });
}

export function verifyToken(issuerPublicKey, presentation, challenge, now) {
  check('TokenPresentation', presentation);
  const isSd = challenge.format === 'sd-jwt-kb';
  const parts = presentation.token.split('~');
  const expectedParts = isSd ? indexesFor(challenge.policy).length + 2 : 2;
  if (parts.length !== expectedParts) {
    throw new Error('Invalid disclosure count');
  }
  const issued = verified(
    parts[0],
    issuerPublicKey,
    isSd ? 'vericlue-lab+sd-jwt' : 'vericlue-lab+jwt',
  );
  if (
    issued.iss !== 'vericlue-lab' ||
    issued.vct !== PROTOCOL ||
    issued.iat > now ||
    issued.exp <= now
  ) {
    throw new Error('Invalid issuer context');
  }
  const holderPublicKey = holderKey(issued.cnf?.jwk);
  const binding = verified(parts.at(-1), holderPublicKey, isSd ? 'kb+jwt' : 'vericlue-lab-pop+jwt');
  const hashName = isSd ? 'sd_hash' : 'token_hash';
  const prefix = `${parts.slice(0, -1).join('~')}~`;
  if (
    binding[hashName] !== digest(prefix) ||
    binding.ctx !== digest(context(challenge)) ||
    binding.aud !== challenge.audience ||
    binding.nonce !== challenge.nonce ||
    !Number.isSafeInteger(binding.iat) ||
    binding.iat < challenge.issued_at ||
    binding.iat > now
  ) {
    throw new Error('Invalid holder binding');
  }
  let claims;
  if (isSd) {
    if (
      issued._sd_alg !== 'sha-256' ||
      !Array.isArray(issued._sd) ||
      issued._sd.length !== CLAIM_NAMES.length ||
      new Set(issued._sd).size !== CLAIM_NAMES.length
    ) {
      throw new Error('Invalid digest list');
    }
    claims = Object.create(null);
    for (const disclosure of parts.slice(1, -1)) {
      const tuple = jsonPart(disclosure);
      if (
        !Array.isArray(tuple) ||
        tuple.length !== 3 ||
        typeof tuple[0] !== 'string' ||
        unb64(tuple[0], 16).length !== 16 ||
        !CLAIM_NAMES.includes(tuple[1]) ||
        Object.hasOwn(claims, tuple[1]) ||
        !issued._sd.includes(digest(disclosure))
      ) {
        throw new Error('Invalid disclosure');
      }
      claims[tuple[1]] = tuple[2];
    }
    check('DisclosedClaims', claims);
    if (Object.keys(claims).length !== indexesFor(challenge.policy).length) {
      throw new Error('Wrong disclosure policy');
    }
  } else {
    claims = check('Claims', issued.claims);
  }
  if (
    claims.valid_from !== issued.iat ||
    claims.valid_until !== issued.exp ||
    !allowed(claims, challenge, now)
  ) {
    throw new Error('Credential policy not met');
  }
  return {
    disclosed: isSd ? claims : structuredClone(claims),
    // Stable issuer JWT is visible in both token schemes; compare directly, not heuristically.
    linkable_artifact: digest(parts[0]),
  };
}

export function visibleTokenClaims(presentation) {
  const parts = presentation.token.split('~');
  return presentation.format === 'jwt-pop'
    ? jsonPart(parts[0].split('.')[1]).claims
    : Object.fromEntries(
        parts.slice(1, -1).map((d) => {
          const [, name, value] = jsonPart(d);
          return [name, value];
        }),
      );
}
