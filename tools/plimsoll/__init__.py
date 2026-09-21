"""Plimsoll 公共 API（阶段 5.2 包入口）。

从仓库根：
    import sys; sys.path.insert(0, "tools")
    import plimsoll
"""

from __future__ import annotations

__version__ = "0.4.2"

# 子模块以脚本式路径加载（tests 将 tools/plimsoll 加入 sys.path）时，
# 这些名字在包内用相对导入；外部经 `plimsoll.xxx` 访问。
try:
    from . import hydrostatics, geometry, geometric, offsets, freesurface, damage  # noqa: F401
except ImportError:  # pragma: no cover - 脚本式 cwd 运行
    import hydrostatics  # noqa: F401
    import geometry  # noqa: F401
    import geometric  # noqa: F401
    import offsets  # noqa: F401
    import freesurface  # noqa: F401
    import damage  # noqa: F401

__all__ = [
    "__version__",
    "hydrostatics",
    "geometry",
    "geometric",
    "offsets",
    "freesurface",
    "damage",
]
