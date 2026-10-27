import {readKeys} from './lib/key-file.mjs';
import {issueVerification} from './lib/verification.mjs';

// Internal pipe only: caller is the authorized API service, never a network listener.
try {
  if (process.argv.length !== 4 || process.argv[2] !== '--key-file')
    throw new Error('Invalid arguments');
  let size = 0;
  const chunks = [];
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > 4096) throw new Error('Request too large');
    chunks.push(chunk);
  }
  const raw = new TextDecoder('utf-8', {fatal: true}).decode(Buffer.concat(chunks));
  const packet = JSON.parse(raw);
  if (Object.keys(packet).sort().join(',') !== 'claims,commitment')
    throw new Error('Invalid request');
  const keys = await readKeys(process.argv[3]);
  const credential = await issueVerification(keys, {commitment: packet.commitment}, packet.claims);
  const output = JSON.stringify(credential);
  if (Buffer.byteLength(output) > 8192) throw new Error('Invalid response');
  process.stdout.write(output);
} catch {
  // Do not expose filesystem paths, keys, input or cryptographic error details.
  process.exitCode = 1;
}
