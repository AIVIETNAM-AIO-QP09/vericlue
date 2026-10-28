import js from '@eslint/js';

export default [
  {ignores: ['dist/**', 'tmp/**']},
  js.configs.recommended,
  {
    files: ['**/*.mjs'],
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: 'module',
      globals: Object.fromEntries(
        [
          'Buffer',
          'console',
          'process',
          'URL',
          'TextEncoder',
          'TextDecoder',
          'structuredClone',
          'Uint8Array',
          'btoa',
          'atob',
          'setTimeout',
        ].map((name) => [name, 'readonly']),
      ),
    },
  },
];
