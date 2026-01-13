#!/usr/bin/env python3
"""Wrapper script to run reconly with proper UTF-8 encoding on Windows."""
import sys
import io

# Force UTF-8 encoding for stdout/stderr on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Import and run the main CLI
from reconly_core.cli.main import main

if __name__ == '__main__':
    main()
