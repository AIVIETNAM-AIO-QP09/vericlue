import {readFileSync, statSync} from 'node:fs';
import {secretKeyToPublicKey} from '@digitalbazaar/bbs-signatures';
import {b64, unb64} from './profile.mjs';

export async function readKeys(path) {
  if (!statSync(path).isFile() || statSync(path).size > 2048) throw new Error('Invalid key file');
  const value = JSON.parse(readFileSync(path, 'utf8'));
  if (
    value.version !== 1 ||
    Object.keys(value).sort().join(',') !== 'public_key,secret_key,version'
  )
    throw new Error('Invalid key bundle');
  const secretKey = unb64(value.secret_key, 32);
  const publicKey = unb64(value.public_key, 96);
  const derived = await secretKeyToPublicKey({secretKey, ciphersuite: 'BLS12-381-SHA-256'});
  if (b64(derived) !== value.public_key) throw new Error('Key mismatch');
  return {secretKey, publicKey};
}
