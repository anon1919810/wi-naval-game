#!/usr/bin/env python3
"""Plimsoll 一键回归（阶段 5.4）。

从任意 cwd：
    python tools/plimsoll/run_all_tests.py
或  python run_all_tests.py  （位于 tools/plimsoll 时）
"""

from __future__ import annotations

import os
import sys
import unittest


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    tests_dir = os.path.join(here, "tests")
    tools_dir = os.path.dirname(here)
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    if here not in sys.path:
        sys.path.insert(0, here)

    loader = unittest.TestLoader()
    suite = loader.discover(tests_dir, pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    n_run = result.testsRun
    n_fail = len(result.failures) + len(result.errors)
    print("PLIMSOLL_REGRESSION run=%d fail=%d" % (n_run, n_fail))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
