import js from '@eslint/js';

export default [
  js.configs.recommended,
  {
    files: ['**/*.mjs'],
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: 'module',
      globals: Object.fromEntries(
        ['Buffer', 'console', 'process', 'URL', 'TextEncoder', 'structuredClone', 'Uint8Array'].map(
          (name) => [name, 'readonly'],
        ),
      ),
    },
  },
];
