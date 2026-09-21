"""Plimsoll · Freeboard 页（v0：干舷与甲板分段）

SPS Freeboard 页（COVERAGE.md §2.2）：甲板分段（Forecastle / Fore / Aft / Quarter deck
的 %Lwl）、艏艉干舷（各 4 行）、甲板型（Flush / Mid break）、船首型/船艉型、
Ram Length、Stern overhang、Depth Unlocked、Sheer 示意图、**Average freeboard（输出）**。

Plimsoll 的做法（诚实记录）
---------------------------
- **Average freeboard**：按各甲板分段的长度加权（段内艏→艉线性，取段均值）——定义式。
- **干舷 ↔ 稳性的桥**：每段给出 `deck_immersion_deg = atan(fb / (B/2))`。
  这是本页与 L1 GZ 的接口：**超过该角后主甲板入水、GZ 曲线不再可信**，
  cli.py 用的是同一判据（半宽取 B/2，是本模块的近似，见 warnings）。
- **本舰数据缺口**：QM 的型深/干舷**没有外部文献源**（Navypedia/维基均不列），
  型深只能由模型型线推得（水线上 5.10 m + 满载吃水 9.9 m = 15.0 m，**estimate**）；
  甲板分段的 %Lwl 与艏艉舷弧（sheer）**未考证** —— 案例里逐项标 estimate。
- 甲板型（Flush/Mid break）、船首/船艉型、Ram length、Stern overhang 是**纯设计输入**，
  不进计算，本模块不做（与 Hull 页"船型滑条"同一处理原则）。

设计纪律（承 SPEC §2，含 §2.7 通用性）：纯函数 dict→dict；输出带 formula/source/estimate；
核心不做四舍五入；**不出现任何具体船只的常量**。
"""

from __future__ import annotations

import math

SCHEMA = "plimsoll-freeboard-1"
VALID_KINDS = ("forecastle", "fore", "aft", "quarterdeck", "other")


def _finite(v, what, positive=False):
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
        raise ValueError("%s 必须是有限数值，收到 %r" % (what, v))
    if positive and v <= 0:
        raise ValueError("%s 必须为正，收到 %r" % (what, v))
    return float(v)


def _T(trace, key, value, formula, source, estimate=False):
    trace.append({"key": key, "value": value, "formula": formula,
                  "source": source, "estimate": estimate})


def from_depth(depth_m: float, draught_m: float) -> dict:
    """干舷 = 型深 − 吃水（定义式；两值须同基准、同为型尺度）。"""
    d = _finite(depth_m, "depth_m", positive=True)
    t = _finite(draught_m, "draught_m", positive=True)
    if t >= d:
        raise ValueError("吃水 %.3f 不小于型深 %.3f：甲板已在水下，干舷无意义" % (t, d))
    trace = []
    _T(trace, "freeboard_m", d - t, "f = D − T", "定义式")
    return {"values": {"freeboard_m": d - t, "depth_m": d, "draught_m": t},
            "trace": trace, "warnings": []}


def compute(case: dict) -> dict:
    """Freeboard 案例 → 分段干舷、加权平均干舷、甲板浸没角。"""
    trace: list[dict] = []
    warnings: list[str] = []

    if case.get("schema") != SCHEMA:
        raise ValueError("schema 必须是 %s，收到 %r" % (SCHEMA, case.get("schema")))

    lwl = _finite(case.get("lwl_m"), "lwl_m", positive=True)
    beam = _finite(case.get("beam_m"), "beam_m", positive=True)
    segs = case.get("segments")
    if not isinstance(segs, list) or not segs:
        raise ValueError("segments 必须是非空数组")

    seen: set[str] = set()
    rows = []
    total_len = 0.0
    total_mom = 0.0
    pct_sum = 0.0
    min_fb = None

    for s in segs:
        sid = s.get("id")
        if not sid:
            raise ValueError("每个分段都要有 id，收到 %r" % (s,))
        if sid in seen:
            raise ValueError("分段 id 重复：%r" % sid)
        seen.add(sid)
        kind = s.get("kind", "other")
        if kind not in VALID_KINDS:
            raise ValueError("分段 %s 的 kind %r 不合法，必须是 %s" % (sid, kind, VALID_KINDS))
        pct = _finite(s.get("length_pct_lwl"), "分段 %s 的 length_pct_lwl" % sid, positive=True)
        fb_f = _finite(s.get("fb_fore_m"), "分段 %s 的 fb_fore_m" % sid)
        fb_a = _finite(s.get("fb_aft_m"), "分段 %s 的 fb_aft_m" % sid)
        if fb_f < 0 or fb_a < 0:
            raise ValueError("分段 %s 的干舷不能为负（收到 %.3f / %.3f）" % (sid, fb_f, fb_a))

        est = bool(s.get("estimate", False))
        src = s.get("source", "无来源")
        length = pct / 100.0 * lwl
        mean_fb = 0.5 * (fb_f + fb_a)
        imm = math.degrees(math.atan(mean_fb / (0.5 * beam)))

        rows.append({"id": sid, "kind": kind, "length_pct_lwl": pct, "length_m": length,
                     "fb_fore_m": fb_f, "fb_aft_m": fb_a, "fb_mean_m": mean_fb,
                     "deck_immersion_deg": imm, "estimate": est, "source": src})
        total_len += length
        total_mom += length * mean_fb
        pct_sum += pct
        min_fb = mean_fb if min_fb is None else min(min_fb, mean_fb)

        _T(trace, "segment.%s.length_m" % sid, length, "L段 = %.2f%% × Lwl" % pct, src, est)
        _T(trace, "segment.%s.fb_mean_m" % sid, mean_fb, "f段 = (f艏 + f艉) / 2", src, est)
        _T(trace, "segment.%s.deck_immersion_deg" % sid, imm,
           "α = atan(f段 / (B/2))", "干舷与半宽之比（半宽取 B/2，近似）", True)
        if mean_fb <= 0:
            warnings.append("分段 %s 的干舷 %.2f m ≤ 0：甲板已在水线，干舷无效。" % (sid, mean_fb))

    avg = total_mom / total_len if total_len > 0 else None
    _T(trace, "average_freeboard_m", avg, "f̄ = Σ(L段·f段) / Σ L段", "长度加权平均",
       any(r["estimate"] for r in rows))
    if avg is not None:
        _T(trace, "min_freeboard_m", min_fb, "min(各段均值)", "分段干舷")
        _T(trace, "deck_immersion_min_deg", math.degrees(math.atan(min_fb / (0.5 * beam))),
           "α = atan(f_min / (B/2))", "最薄弱段的甲板浸没角", True)

    if abs(pct_sum - 100.0) > 1e-6:
        warnings.append("各段 length_pct_lwl 合计 %.1f%% ≠ 100%%：加权平均只覆盖已声明的段。" % pct_sum)
    if avg is not None and avg <= 0:
        warnings.append("平均干舷 %.2f m ≤ 0。" % avg)
    imm_min = math.degrees(math.atan(min_fb / (0.5 * beam))) if min_fb is not None else None
    if imm_min is not None and imm_min < 15.0:
        warnings.append("最薄弱段甲板浸没角仅 %.1f°：GZ 曲线在该角以上已不可信（甲板入水）。" % imm_min)

    return {
        "values": {"average_freeboard_m": avg, "min_freeboard_m": min_fb,
                   "deck_immersion_min_deg": imm_min,
                   "covered_pct_lwl": pct_sum, "segments": len(rows)},
        "segments": rows,
        "trace": trace,
        "warnings": warnings,
    }


def sps_view(result: dict) -> dict:
    """compute() 结果 → SPS Freeboard 页视图（分段行 + Average freeboard）。"""
    return {
        "segments": [{"id": r["id"], "kind": r["kind"], "length_pct_lwl": r["length_pct_lwl"],
                      "fb_fore_m": r["fb_fore_m"], "fb_aft_m": r["fb_aft_m"],
                      "deck_immersion_deg": r["deck_immersion_deg"]}
                     for r in result["segments"]],
        "average_freeboard_m": result["values"]["average_freeboard_m"],
    }
