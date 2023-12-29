# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
extends: default

ignore-from-file: [.gitignore, .yamlignore]

rules:
  document-start: disable
  octal-values: enable
  truthy:
    allowed-values: ['true', 'false', 'on']  # 'on' for GH action trigger
  line-length:
    max: 200
  indentation:
    check-multi-line-strings: false
    indent-sequences: consistent
  brackets:
    max-spaces-inside: 1
    max-spaces-inside-empty: 0
  braces:
    max-spaces-inside: 1
    max-spaces-inside-empty: 0
