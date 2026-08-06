"""Shared fixtures."""
from __future__ import annotations

import os
import sys

# Make the project root importable when pytest is invoked from anywhere.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
