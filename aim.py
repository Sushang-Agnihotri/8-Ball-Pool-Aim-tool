#!/usr/bin/env python3
"""Backward-compatible launcher: ``python aim.py`` (or ``python -m pool_aim``)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from pool_aim.app import main

if __name__ == "__main__":
    main()
