import {createVerificationWallet, HolderError} from './holder.mjs';

const fail = (code) => {
  throw new HolderError(code);
};
const now = () => Math.floor(Date.now() / 1000);

/** Headless orchestration; transport owns authenticated HTTP, never holder secrets. */
export async function createVerificationSession({
  transport,
  signDevice,
  requestTimeoutMs = 10000,
  ...options
}) {
  if (
    typeof transport?.authorize !== 'function' ||
    typeof transport?.issue !== 'function' ||
    typeof signDevice !== 'function' ||
    !Number.isInteger(requestTimeoutMs) ||
    requestTimeoutMs < 1 ||
    requestTimeoutMs > 15000
  )
    fail('holder_invalid_context');
  const api = {
    authorize: transport.authorize.bind(transport),
    issue: transport.issue.bind(transport),
  };
  const clock = options.clock ?? now;
  const wallet = await createVerificationWallet({...options, clock});
  return new Session(wallet, api, signDevice, clock, requestTimeoutMs);
}

class Session {
  #wallet;
  #api;
  #sign;
  #clock;
  #timeout;
  #notBefore = 0;
  #action = null;
  #closed = false;
  #offer = null;
  #request = null;

  constructor(wallet, api, sign, clock, timeout) {
    this.#wallet = wallet;
    this.#api = api;
    this.#sign = sign;
    this.#clock = clock;
    this.#timeout = timeout;
    this.#notBefore = this.#check();
  }

  metadata() {
    return this.#wallet.metadata();
  }

  #check() {
    if (this.#closed) fail('holder_closed');
    const value = this.#clock();
    if (!Number.isSafeInteger(value) || value < 0) {
      this.destroy();
      fail('holder_invalid_clock');
    }
    if (value < this.#notBefore || value >= this.metadata().expires_at) {
      this.destroy();
      fail('holder_expired');
    }
    return value;
  }

  async #wait(operation, action, network = false) {
    const remaining = (this.metadata().expires_at - this.#check()) * 1000;
    const requestLimit = network && this.#timeout < remaining;
    let timer, cancel;
    const interrupted = new Promise((resolve, reject) => {
      cancel = () =>
        reject(new HolderError(this.#closed ? 'holder_closed' : 'holder_request_timeout'));
      action.signal.addEventListener('abort', cancel, {once: true});
      timer = setTimeout(
        () => {
          if (requestLimit) {
            reject(new HolderError('holder_request_timeout'));
            action.abort();
          } else {
            reject(new HolderError('holder_expired'));
            this.destroy();
          }
        },
        requestLimit ? this.#timeout : remaining,
      );
    });
    try {
      return await Promise.race([
        interrupted,
        Promise.resolve().then(() => {
          this.#check();
          if (action.signal.aborted) fail('holder_request_timeout');
          return operation();
        }),
      ]);
    } finally {
      clearTimeout(timer);
      action.signal.removeEventListener('abort', cancel);
    }
  }

  async #run(operation) {
    this.#check();
    if (this.#action) fail('holder_busy');
    const action = new AbortController();
    this.#action = action;
    try {
      const value = await operation(action);
      this.#check();
      return value;
    } catch (error) {
      if (error instanceof HolderError) throw error;
      fail(this.#closed ? 'holder_closed' : 'holder_request_failed');
    } finally {
      if (this.#action === action) this.#action = null;
    }
  }

  async issue({consent} = {}) {
    if (consent !== true) fail('holder_consent_required');
    return this.#run(async (action) => {
      if (this.metadata().state === 'issued') return this.metadata();
      if (!this.#offer)
        this.#offer = await this.#wait(() => this.#wallet.prepare({consent: true}), action);
      if (!this.#request) {
        const authorization = await this.#wait(
          () => this.#api.authorize(structuredClone(this.#offer), {signal: action.signal}),
          action,
          true,
        );
        this.#request = await this.#wait(
          () => this.#wallet.authorize(authorization, this.#sign),
          action,
        );
      }
      const credential = await this.#wait(
        () => this.#api.issue(structuredClone(this.#request), {signal: action.signal}),
        action,
        true,
      );
      await this.#wait(() => this.#wallet.accept(credential), action);
      this.#offer = this.#request = null;
      return this.metadata();
    });
  }

  async present(challenge, options) {
    return this.#run((action) =>
      this.#wait(() => this.#wallet.present(challenge, options), action),
    );
  }

  destroy() {
    this.#closed = true;
    this.#wallet.destroy();
    this.#offer = this.#request = this.#api = this.#sign = null;
    this.#action?.abort();
  }
}
