import {performance} from 'node:perf_hooks';
import {issuerKeys, issueBbs, prepareHolder, presentBbs} from './bbs.mjs';
import {demoClaims, PRIVATE_FIELDS} from './profile.mjs';
import {issueToken, presentToken, tokenKeys, visibleTokenClaims} from './tokens.mjs';
import {Verifier} from './verifier.mjs';

const wire = (value) => JSON.parse(JSON.stringify(value));
const size = (value) => Buffer.byteLength(JSON.stringify(value));
const median = (values) => {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
};

export async function runDemo({runs = 5, clock = () => Math.floor(Date.now() / 1000)} = {}) {
  if (!Number.isSafeInteger(runs) || runs < 1 || runs > 100) {
    throw new Error('runs must be between 1 and 100');
  }
  const bbsKeys = await issuerKeys();
  const signingKeys = tokenKeys();
  const baselineHolder = tokenKeys();
  const {offer, holder} = await prepareHolder();
  const claims = demoClaims('adult', clock());
  const started = performance.now();
  const bbsCredential = wire(await issueBbs(bbsKeys, wire(offer), claims));
  const bbsIssueMs = performance.now() - started;
  const verifiers = ['https://service-a.example', 'https://service-b.example'].map(
    (audience) =>
      new Verifier({
        audience,
        bbsPublicKey: bbsKeys.publicKey,
        tokenPublicKey: signingKeys.publicKey,
        clock,
      }),
  );
  const rows = [];
  for (const format of ['jwt-pop', 'sd-jwt-kb', 'bbs-nym']) {
    const credential =
      format === 'bbs-nym'
        ? bbsCredential
        : issueToken(signingKeys, baselineHolder.publicKey, claims, format);
    const generation = [];
    const verification = [];
    const sizes = [];
    const results = [];
    const presentations = [];
    for (let i = 0; i < runs + 1; i++) {
      const verifier = verifiers[i === runs ? 1 : 0];
      const challenge = wire(verifier.challenge(format));
      const start = performance.now();
      const presentation = wire(
        format === 'bbs-nym'
          ? await presentBbs(bbsKeys.publicKey, credential, holder, challenge)
          : presentToken(credential, baselineHolder.privateKey, challenge),
      );
      const generated = performance.now();
      const result = await verifier.verify(wire(presentation));
      const finished = performance.now();
      if (!result.valid) {
        throw new Error(`Demo verification failed for ${format}`);
      }
      const replay = await verifier.verify(wire(presentation));
      if (replay.valid) {
        throw new Error('Demo replay unexpectedly accepted');
      }
      presentations.push(presentation);
      results.push(result);
      if (i < runs) {
        generation.push(generated - start);
        verification.push(finished - generated);
        sizes.push(size(presentation));
      }
    }
    const visible =
      format === 'bbs-nym' ? presentations[0].disclosed : visibleTokenClaims(presentations[0]);
    rows.push({
      format,
      samples: runs,
      generate_ms: generation,
      verify_ms: verification,
      generate_median_ms: median(generation),
      verify_median_ms: median(verification),
      presentation_bytes: sizes,
      presentation_median_bytes: median(sizes),
      personal_fields_visible: PRIVATE_FIELDS.filter((name) => Object.hasOwn(visible, name)),
      cryptographic_verifications: runs + 1,
      replay_rejections: runs + 1,
      same_issuer_token_across_services:
        format === 'bbs-nym'
          ? null
          : results[0].linkable_artifact === results.at(-1).linkable_artifact,
      pseudonym_same_service:
        format === 'bbs-nym' && runs > 1 ? results[0].pseudonym === results[1].pseudonym : null,
      pseudonym_different_services:
        format === 'bbs-nym' ? results[0].pseudonym !== results.at(-1).pseudonym : null,
      // Different bytes demonstrate randomization, not an empirical proof of unlinkability.
      randomized_proof_bytes:
        format === 'bbs-nym' && runs > 1 ? presentations[0].proof !== presentations[1].proof : null,
    });
  }
  return {
    assurance: 'synthetic-demo',
    profile: claims.protocol,
    measured_at: new Date(clock() * 1000).toISOString(),
    scenarios: {
      issuer: 'vericlue-lab',
      verifier_count: 2,
      persona: 'synthetic adult',
      policy: 'adult',
    },
    bbs_issue_ms: bbsIssueMs,
    comparison: rows,
    limits: [
      'Chỉ đo mật mã trên persona tổng hợp; không phải độ chính xác eKYC.',
      'BBS dùng profile riêng, không tuyên bố tuân thủ toàn bộ W3C VC/JSON-LD.',
      'Nonce chỉ giữ trong RAM của một verifier; restart mất lượt chờ, chưa dùng production.',
      'BBS không kháng lượng tử; bí mật holder chưa được chứng thực bằng phần cứng.',
      'age_over_18 do issuer tính và ký, không phải range proof trên ngày sinh ẩn.',
      'Không đo hay bảo đảm chống liên kết qua IP, metadata hoặc thông tin tự tiết lộ.',
      'Thời gian đo gồm kiểm profile/serialization, chưa đo mạng/điện thoại; không dùng làm SLA.',
    ],
  };
}
