import {check} from './contract.mjs';
import {verifyBbs} from './bbs.mjs';
import {verifyToken} from './tokens.mjs';
import {CHALLENGE_TTL, MAX_PENDING, origin, randomId} from './profile.mjs';

export class Verifier {
  #pending = new Map();
  #bbsKey;
  #tokenKey;
  #clock;
  #audience;

  constructor({
    audience,
    bbsPublicKey,
    tokenPublicKey,
    clock = () => Math.floor(Date.now() / 1000),
  }) {
    this.#audience = origin(audience);
    this.#bbsKey = new Uint8Array(bbsPublicKey);
    if (this.#bbsKey.length !== 96 || !tokenPublicKey) {
      throw new Error('Trusted issuer public keys are required');
    }
    this.#tokenKey = tokenPublicKey;
    this.#clock = clock;
  }

  challenge(format, policy = 'adult') {
    const now = this.#clock();
    for (const [id, entry] of this.#pending) {
      if (entry.challenge.expires_at <= now) {
        this.#pending.delete(id);
      }
    }
    if (this.#pending.size >= MAX_PENDING) {
      throw new Error('Challenge capacity reached');
    }
    const challenge = check('Challenge', {
      id: randomId(16),
      nonce: randomId(32),
      audience: this.#audience,
      format,
      policy,
      issued_at: now,
      expires_at: now + CHALLENGE_TTL,
    });
    this.#pending.set(challenge.id, {challenge: structuredClone(challenge), busy: false});
    return structuredClone(challenge);
  }

  async verify(presentation) {
    let entry;
    let reserved = false;
    try {
      check(
        presentation?.format === 'bbs-nym' ? 'BbsPresentation' : 'TokenPresentation',
        presentation,
      );
      entry = this.#pending.get(presentation.challenge_id);
      const now = this.#clock();
      if (
        !entry ||
        entry.busy ||
        entry.challenge.expires_at <= now ||
        entry.challenge.issued_at > now
      ) {
        return {valid: false, reason: 'challenge_unavailable'};
      }
      const {challenge} = entry;
      if (challenge.format !== presentation.format) {
        return {valid: false, reason: 'invalid_presentation'};
      }
      // Reserve synchronously before awaiting native crypto; only one concurrent request wins.
      entry.busy = true;
      reserved = true;
      let result;
      if (presentation.format === 'bbs-nym') {
        if (!(await verifyBbs(this.#bbsKey, presentation, challenge, now))) {
          throw new Error('Invalid BBS proof');
        }
        result = {
          disclosed: structuredClone(presentation.disclosed),
          pseudonym: presentation.pseudonym,
        };
      } else {
        result = verifyToken(this.#tokenKey, presentation, challenge, now);
      }
      const finished = this.#clock();
      if (
        finished < challenge.issued_at ||
        finished >= challenge.expires_at ||
        finished >= result.disclosed.valid_until ||
        this.#pending.get(challenge.id) !== entry
      ) {
        throw new Error('Context expired during verification');
      }
      this.#pending.delete(challenge.id);
      return {valid: true, assurance: 'synthetic-demo', ...result};
    } catch {
      return {valid: false, reason: 'invalid_presentation'};
    } finally {
      if (reserved) {
        entry.busy = false;
      }
    }
  }
}
