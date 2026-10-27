import {mkdirSync, writeFileSync, existsSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {issuerKeys} from './lib/bbs.mjs';
import {b64} from './lib/profile.mjs';
import {readKeys} from './lib/key-file.mjs';

if (process.argv.includes('--help')) {
  console.log(
    'Tạo khóa BBS riêng cho cấp chứng nhận. Không tự áp dụng cấu hình.\nnode keygen.mjs --out secrets/private-credentials/bbs.json',
  );
} else {
  try {
    if (process.argv.length !== 4 || process.argv[2] !== '--out')
      throw new Error('Invalid arguments');
    const path = resolve(process.argv[3]);
    if (existsSync(path)) {
      await readKeys(path);
      console.log('Bộ khóa đã có và hợp lệ; giữ nguyên.');
    } else {
      const keys = await issuerKeys();
      mkdirSync(dirname(path), {recursive: true, mode: 0o700});
      writeFileSync(
        path,
        JSON.stringify({
          version: 1,
          secret_key: b64(keys.secretKey),
          public_key: b64(keys.publicKey),
        }),
        {flag: 'wx', mode: 0o600},
      );
      console.log('Đã tạo bộ khóa BBS. Không chia sẻ hoặc commit tệp bí mật.');
    }
  } catch {
    console.error('Không tạo hoặc kiểm được bộ khóa; không ghi đè.');
    process.exitCode = 1;
  }
}
