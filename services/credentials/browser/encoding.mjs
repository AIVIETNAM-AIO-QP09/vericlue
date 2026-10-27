export const bytes = (value) => new TextEncoder().encode(value);
export const text = (value) => new TextDecoder('utf-8', {fatal: true}).decode(value);
export const hex = (value) => Array.from(value, (b) => b.toString(16).padStart(2, '0')).join('');
export const hash = async (value) =>
  hex(new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', value)));
export const canonical = (value) =>
  JSON.stringify(
    Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((k) => [k, value[k]]),
    ),
  );

export function base64(value) {
  return btoa(Array.from(value, (b) => String.fromCharCode(b)).join(''));
}

export const b64 = (value) =>
  base64(value).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '');

export function decode(value, {url = true, size, max = 4096} = {}) {
  if (
    typeof value !== 'string' ||
    !value.length ||
    value.length > max ||
    (url && !/^[A-Za-z0-9_-]+$/.test(value))
  )
    throw new Error('Invalid encoding');
  const normalized = url
    ? value.replaceAll('-', '+').replaceAll('_', '/') + '='.repeat((4 - (value.length % 4)) % 4)
    : value;
  const result = Uint8Array.from(atob(normalized), (c) => c.charCodeAt(0));
  if (
    (url ? b64(result) : base64(result)) !== value ||
    (size !== undefined && result.length !== size)
  )
    throw new Error('Invalid encoding');
  return result;
}

export function origin(value) {
  const url = new URL(value);
  if (value.length > 200 || url.protocol !== 'https:' || url.origin !== value)
    throw new Error('Invalid audience');
  return value;
}

export function p256Der(raw) {
  if (!(raw instanceof Uint8Array) || raw.length !== 64)
    throw new Error('P-256 signature required');
  const integer = (part) => {
    let start = 0;
    while (start < part.length - 1 && part[start] === 0) start++;
    const value = Array.from(part.subarray(start));
    if (value[0] & 128) value.unshift(0);
    return [2, value.length, ...value];
  };
  const r = integer(raw.subarray(0, 32)),
    s = integer(raw.subarray(32));
  return new Uint8Array([48, r.length + s.length, ...r, ...s]);
}
