import {readFileSync, mkdirSync, writeFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {dirname, resolve} from 'node:path';
import Ajv2020 from 'ajv/dist/2020.js';
import standaloneCode from 'ajv/dist/standalone/index.js';
import {build} from 'esbuild';

const root = fileURLToPath(new URL('../', import.meta.url));
const schemas = resolve(root, '../../packages/contracts/schemas');
// ResultClaims' allOf/then intentionally requires properties declared on its parent.
// Disable only this schema-lint restriction; actual required-field checks remain compiled.
const ajv = new Ajv2020({strict: true, strictRequired: false, code: {source: true, esm: true}});
const entries = {};
for (const [file, names] of [
  [
    'credential',
    [
      'HolderExpectedContext',
      'CredentialAuthorizationContext',
      'CredentialAuthorization',
      'CredentialKey',
      'VerificationCredential',
      'VerificationChallenge',
      'VerificationPresentation',
    ],
  ],
  ['result', ['SigningKey', 'SignedResult', 'ResultClaims']],
]) {
  const schema = JSON.parse(readFileSync(resolve(schemas, file + '.schema.json'), 'utf8'));
  ajv.addSchema(schema);
  for (const name of names) entries[name] = `${schema.$id}#/$defs/${name}`;
}
const validators = resolve(root, 'tmp/holder-validators.mjs');
mkdirSync(dirname(validators), {recursive: true});
writeFileSync(validators, standaloneCode(ajv, entries));
const bbsRoot = dirname(createRequire(import.meta.url).resolve('@digitalbazaar/bbs-signatures'));
const aliases = {
  '#holder-validators': validators,
  '#bbs-nym': resolve(bbsRoot, 'bbs/pseudonym/interface.js'),
  '#bbs-suite': resolve(bbsRoot, 'bbs/ciphersuites.js'),
};
const result = await build({
  absWorkingDir: root,
  entryPoints: ['browser/holder.mjs'],
  outfile: 'dist/holder.mjs',
  platform: 'browser',
  format: 'esm',
  bundle: true,
  minify: true,
  target: 'es2022',
  legalComments: 'eof',
  metafile: true,
  plugins: [
    {
      name: 'pinned-bbs-holder',
      setup(builder) {
        builder.onResolve({filter: /^#(holder-validators|bbs-nym|bbs-suite)$/}, ({path}) => ({
          path: aliases[path],
        }));
      },
    },
  ],
});
writeFileSync(
  resolve(root, 'dist/holder.d.mts'),
  readFileSync(resolve(root, 'browser/holder.d.mts')),
);
if (Object.values(result.metafile.outputs).some((o) => o.imports.some((i) => i.external)))
  throw new Error('Holder bundle must be self-contained');
if (
  !Object.keys(result.metafile.inputs).some((p) =>
    p.endsWith('bbs-signatures/lib/crypto-browser.js'),
  )
)
  throw new Error('Browser CSPRNG adapter not bundled');
// Ship complete license texts alongside the distributable, including generated AJV code.
const licenses = [
  '@digitalbazaar/bbs-signatures',
  '@noble/curves',
  '@noble/hashes',
  'ajv',
  'esbuild',
];
writeFileSync(
  resolve(root, 'dist/LICENSES.txt'),
  licenses
    .map(
      (name) =>
        `${name}\n\n${readFileSync(resolve(root, 'node_modules', name, name === 'esbuild' ? 'LICENSE.md' : 'LICENSE'), 'utf8')}`,
    )
    .join('\n\n====================\n\n'),
);
console.log('Built standalone browser holder with pinned BBS and precompiled contracts.');
