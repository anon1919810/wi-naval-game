"""Plimsoll 公共 API（阶段 5.2 包入口）。

从仓库根：
    import sys
    sys.path.insert(0, "tools")   # 使 plimsoll 成为包
    import plimsoll
    plimsoll.damage.flood_combination(...)
"""

from __future__ import annotations

import os
import sys

__version__ = "0.4.2"

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.dirname(_PKG_DIR)
for _p in (_TOOLS_DIR, _PKG_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 内部模块为脚式绝对名（geometry/geometric/...），故先把包目录入 path，
# 再同时以包属性与顶层名暴露，保证两种导入方式都可调用。
import hydrostatics  # noqa: E402
import geometry  # noqa: E402
import geometric  # noqa: E402
import offsets  # noqa: E402
import freesurface  # noqa: E402
import damage  # noqa: E402

__all__ = [
    "__version__",
    "hydrostatics",
    "geometry",
    "geometric",
    "offsets",
    "freesurface",
    "damage",
]