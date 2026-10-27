import {execFileSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {cpus, platform, arch} from 'node:os';
import {runDemo} from './lib/demo.mjs';

const args = process.argv.slice(2);
if (args.length === 0 || args.includes('--help')) {
  console.log(
    'VeriClue — thử nghiệm chứng nhận riêng tư, chỉ dữ liệu tổng hợp.\n' +
      'node cli.mjs demo [--runs 1..100]\n' +
      'In JSON so sánh JWT+PoP, SD-JWT+KB và BBS; không ghi khóa hoặc credential.',
  );
} else if (
  args[0] !== 'demo' ||
  (args.length !== 1 && !(args.length === 3 && args[1] === '--runs' && /^\d+$/.test(args[2])))
) {
  console.error('Tham số không hợp lệ; dùng --help.');
  process.exitCode = 2;
} else {
  try {
    const report = await runDemo({runs: args.length === 3 ? Number(args[2]) : 5});
    const root = new URL('../../', import.meta.url);
    let commit = 'unknown';
    let dirty = null;
    try {
      commit = execFileSync('git', ['rev-parse', 'HEAD'], {
        cwd: root,
        encoding: 'utf8',
        timeout: 5000,
      }).trim();
      dirty =
        execFileSync(
          'git',
          [
            'status',
            '--porcelain',
            '--',
            'services/credentials',
            'packages/contracts/schemas/private_credential.schema.json',
          ],
          {cwd: root, encoding: 'utf8', timeout: 5000},
        ).trim().length > 0;
    } catch {
      // Measurement remains labelled unknown if Git is unavailable; never fabricate provenance.
    }
    const lock = JSON.parse(readFileSync(new URL('package-lock.json', import.meta.url), 'utf8'));
    report.runtime = {
      node: process.version,
      platform: platform(),
      arch: arch(),
      cpu: cpus()[0]?.model ?? 'unknown',
      code_commit: commit,
      code_dirty: dirty,
      dependencies: Object.fromEntries(
        Object.entries(lock.packages)
          .filter(([name]) => name)
          .map(([name, value]) => [name.replace('node_modules/', ''), value.version]),
      ),
    };
    console.log(JSON.stringify(report, null, 2));
  } catch {
    console.error('Thử nghiệm thất bại; không xuất credential hoặc bí mật.');
    process.exitCode = 1;
  }
}
