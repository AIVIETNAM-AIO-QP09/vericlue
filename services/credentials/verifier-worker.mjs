import {unb64} from './lib/profile.mjs';
import {verifyVerification} from './lib/verification.mjs';

// Public key only. The API owns authorization, durable state and transaction commit.
try {
  if (process.argv.length !== 2) throw new Error('Invalid arguments');
  let size = 0;
  const chunks = [];
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > 4096) throw new Error('Request too large');
    chunks.push(chunk);
  }
  const packet = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(Buffer.concat(chunks)));
  if (Object.keys(packet).sort().join(',') !== 'audience,challenge,issuer,presentation,public_key')
    throw new Error('Invalid packet');
  const result = await verifyVerification({
    publicKey: unb64(packet.public_key, 96),
    issuer: packet.issuer,
    audience: packet.audience,
    challenge: packet.challenge,
    presentation: packet.presentation,
  });
  process.stdout.write(JSON.stringify(result));
} catch {
  process.exitCode = 1;
}
