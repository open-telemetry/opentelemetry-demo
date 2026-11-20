// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { defineConfig, globalIgnores } from 'eslint/config';
import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';
import nextTypescript from 'eslint-config-next/typescript';
import react from 'eslint-plugin-react';

export default defineConfig([
  globalIgnores(['.next/**', 'next-env.d.ts', 'protos/**']),
  react.configs.flat.recommended,
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    rules: {
      '@typescript-eslint/no-non-null-assertion': 'off',
      'react-hooks/exhaustive-deps': 'warn',
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': 'error',
      'max-len': [
        'error',
        {
          code: 150,
          ignoreComments: true,
          ignoreTrailingComments: true,
          ignoreUrls: true,
          ignoreStrings: true,
          ignoreTemplateLiterals: true,
        },
      ],
    },
  },
  {
    files: ['**/*.js'],
    rules: {
      '@typescript-eslint/no-require-imports': 'off',
    },
  },
  {
    files: ['cypress/**'],
    rules: {
      '@typescript-eslint/no-unused-expressions': 'off',
    },
  },
]);
