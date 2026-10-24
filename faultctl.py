#!/usr/bin/env python3
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Root launcher – run from the repository root as ``python faultctl.py``."""

import sys
from pathlib import Path

# Ensure src/ is on the import path so ``from faultctl import …`` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from faultctl.cli import main

main()
