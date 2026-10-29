// Private test IPC: holder secrets never appear in HTTP requests or test output.
import { prepareHolder } from "../../credentials/lib/bbs.mjs";
import { b64, unb64 } from "../../credentials/lib/profile.mjs";
import {
  presentVerification,
  VerificationVerifier,
} from "../../credentials/lib/verification.mjs";

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const input = JSON.parse(Buffer.concat(chunks).toString("utf8"));
if (input.op === "prepare") {
  const { offer, holder } = await prepareHolder();
  process.stdout.write(
    JSON.stringify({
      offer,
      state: {
        secret: b64(holder.holderSecret),
        prover: holder.proverNym.toString(16),
        blind: holder.blinding.toString(16),
      },
    }),
  );
} else if (input.op === "verify" || input.op === "present") {
  const holder = {
    holderSecret: unb64(input.state.secret),
    proverNym: BigInt("0x" + input.state.prover),
    blinding: BigInt("0x" + input.state.blind),
  };
  const publicKey = unb64(input.key.public_key, 96);
  if (input.op === "present") {
    process.stdout.write(
      JSON.stringify(
        await presentVerification(
          publicKey,
          input.credential,
          holder,
          input.challenge,
        ),
      ),
    );
  } else {
    const v = new VerificationVerifier({
      publicKey,
      issuer: input.credential.claims.issuer,
      audience: "https://service.example",
      clock: () => input.now,
    });
    const p = await presentVerification(
      publicKey,
      input.credential,
      holder,
      v.challenge(),
    );
    const result = await v.verify(p);
    process.stdout.write(
      JSON.stringify({
        valid: result.valid,
        replay: (await v.verify(p)).valid,
        disclosed: Object.keys(result.disclosed ?? {}),
      }),
    );
  }
} else throw new Error("Unknown test operation");
