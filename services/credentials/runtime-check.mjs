import {createHash} from 'node:crypto';
import {readFileSync, statSync} from 'node:fs';
import {nym, suite} from './lib/bbs.mjs';
import {readKeys} from './lib/key-file.mjs';
import {checkCredential} from './lib/contract.mjs';
import {unb64} from './lib/profile.mjs';

// Read-only: verify a public conformance vector; never issue using deployment keys.
try {
  const [major, minor] = process.versions.node.split('.').map(Number);
  if (!((major === 22 && minor >= 13) || major >= 24)) throw new Error('Node version');
  const args = process.argv.slice(2);
  const options = {};
  for (let i = 0; i < args.length; i += 2) {
    const name = args[i];
    if (
      !['--issuer-key-file', '--verifier-public-key-file'].includes(name) ||
      !args[i + 1] ||
      name in options
    )
      throw new Error('Arguments');
    options[name] = args[i + 1];
  }
  const vector = JSON.parse(
    readFileSync(
      new URL('../../packages/contracts/test-vectors/bbs-nym-public-v1.json', import.meta.url),
      'utf8',
    ),
  );
  const bytes = (value) => new Uint8Array(Buffer.from(value, 'hex'));
  const params = {
    ...Object.fromEntries(
      ['PK', 'header', 'ph', 'context_id', 'pseudonym', 'proof'].map((name) => [
        name,
        bytes(vector[name]),
      ]),
    ),
    L: vector.L,
    disclosed_indexes: vector.disclosed_indexes,
    disclosed_committed_indexes: vector.disclosed_committed_indexes,
    disclosed_messages: vector.disclosed_messages.map(bytes),
    disclosed_committed_messages: vector.disclosed_committed_messages.map(bytes),
    ciphersuite: suite,
  };
  if (!(await nym.ProofVerifyWithPseudonym(params))) throw new Error('Conformance');
  const context_id = params.context_id.slice();
  context_id[0] ^= 1;
  if (await nym.ProofVerifyWithPseudonym({...params, context_id})) throw new Error('Context');
  const output = {runtime_ok: true, issuer_key_id: null, verifier_key_id: null};
  if (options['--issuer-key-file']) {
    const keys = await readKeys(options['--issuer-key-file']);
    output.issuer_key_id = createHash('sha256').update(keys.publicKey).digest('hex');
    keys.secretKey.fill(0);
  }
  if (options['--verifier-public-key-file']) {
    const path = options['--verifier-public-key-file'];
    if (!statSync(path).isFile() || statSync(path).size > 2048) throw new Error('Pin size');
    const raw = readFileSync(path);
    if (raw.length > 2048) throw new Error('Pin size');
    const pin = checkCredential('CredentialKey', JSON.parse(raw));
    if (createHash('sha256').update(unb64(pin.public_key, 96)).digest('hex') !== pin.key_id)
      throw new Error('Pin');
    output.verifier_key_id = pin.key_id;
  }
  console.log(JSON.stringify(output));
} catch {
  console.error('credential_runtime_check_failed');
  process.exitCode = 2;
}
