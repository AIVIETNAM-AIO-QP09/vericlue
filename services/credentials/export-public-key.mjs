import {createHash} from 'node:crypto';
import {writeFileSync} from 'node:fs';
import {readKeys} from './lib/key-file.mjs';
import {checkCredential} from './lib/contract.mjs';
import {b64} from './lib/profile.mjs';

try {
  if (process.argv.length !== 6 || process.argv[2] !== '--key-file' || process.argv[4] !== '--out')
    throw new Error('Invalid arguments');
  const {publicKey} = await readKeys(process.argv[3]);
  const value = checkCredential('CredentialKey', {
    algorithm: 'BBS-BLS12-381-SHA-256-NYM',
    key_id: createHash('sha256').update(publicKey).digest('hex'),
    public_key: b64(publicKey),
  });
  writeFileSync(process.argv[5], JSON.stringify(value) + '\n', {flag: 'wx', mode: 0o644});
  console.log('Đã xuất khóa công khai; chuyển tệp này tới bên kiểm chứng qua kênh tin cậy.');
} catch {
  console.error('Không xuất được khóa công khai; không ghi đè tệp đã có.');
  process.exitCode = 1;
}
