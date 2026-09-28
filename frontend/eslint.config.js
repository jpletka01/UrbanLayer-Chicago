import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      // React Compiler advisories (eslint-plugin-react-hooks v6+). They flag
      // patterns that are valid React today but block automatic memoization,
      // e.g. syncing derived state in an effect. Existing code predates the
      // compiler, so they're warnings: CI caps the warning count
      // (`npm run lint`) so it can only go down, and new code should follow
      // them. rules-of-hooks stays an error.
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/refs': 'warn',
      'react-hooks/preserve-manual-memoization': 'warn',
      'react-hooks/immutability': 'warn',
      // Fast-refresh hint for files that export both components and helpers.
      'react-refresh/only-export-components': 'warn',
    },
  },
])
