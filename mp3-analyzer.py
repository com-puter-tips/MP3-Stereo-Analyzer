#!/usr/bin/env python3
"""Backward-compatible entry point.

The analysis logic now lives in the importable module ``mp3_stereo_analyzer``
(installed via ``pip install mp3-stereo-analyzer``). This wrapper keeps the
original ``python3 mp3-analyzer.py file.mp3`` invocation working.
"""
from mp3_stereo_analyzer import main

if __name__ == "__main__":
    main()
