// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTypeScript from 'eslint-config-next/typescript';

const config = [
  ...nextVitals,
  ...nextTypeScript,
  {
    ignores: ['protos/**', 'cypress/screenshots/**', 'cypress/videos/**'],
  },
  {
    files: ['**/*.{js,jsx,mjs,ts,tsx,mts,cts}'],
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
    files: ['**/*.cjs', 'next.config.js', 'utils/telemetry/Instrumentation.js'],
    rules: { '@typescript-eslint/no-require-imports': 'off' },
  },
];

export default config;
