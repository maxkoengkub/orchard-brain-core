"""Convenience entry point — delegates to the orchard_brain CLI.

Run ``python main.py --help`` for options, or use the installed
``orchard-brain`` console script.
"""
from src.orchard_brain.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
