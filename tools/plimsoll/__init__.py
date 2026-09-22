"""Plimsoll 公共 API（阶段 5.2 包入口）。

从仓库根：
    import sys
    sys.path.insert(0, "tools")   # 使 plimsoll 成为包
    import plimsoll
    plimsoll.damage.flood_combination(...)
"""

from __future__ import annotations

__version__ = "0.4.2"

from . import damage, freesurface, geometric, geometry, hydrostatics, offsets

__all__ = [
    "__version__",
    "hydrostatics",
    "geometry",
    "geometric",
    "offsets",
    "freesurface",
    "damage",
]
