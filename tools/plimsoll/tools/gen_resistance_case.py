"""Generate normal-loading resistance estimate and a separate model-loading comparison."""
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))
import resistance as R
from tools.qm_resistance_inputs import load_inputs, read_case

OUT = PKG / "cases/queen_mary_1913_resistance.json"


def main():
    hp, assumptions, trial = load_inputs()
    fc = read_case("queen_mary_1913_formcoeff.json")
    fv = fc["values"]
    model = {
        "lwl_m": fv["lwl_m"], "s_m2": fv["wetted_surface_m2"], "cp": fv["cp"],
        "bt": fv["beam_wl_m"] / fv["draught_at_wl_m"],
        "volumetric": fv["volume_m3"] / fv["lwl_m"] ** 3,
        "loading_condition": fc["loading_condition"], "estimate": True,
        "warnings": fc["warnings"], "sources": {"geometry": "queen_mary_1913_formcoeff.json"},
    }
    tg = read_case("taylor_gertler_cr_table.json")
    v_kn, shp, qpc = trial["speed_kn"], trial["shp"], assumptions["qpc"]
    normal = R.speed_power_curve(hp, [v_kn], tg, qpc=qpc)
    comparison = R.speed_power_curve(model, [v_kn], tg, qpc=qpc)
    row, mr = normal["rows"][0], comparison["rows"][0]
    imp = R.implied_residual_from_trial(shp, v_kn, row["rf_kN"] * 1000., hp["s_m2"], qpc=qpc)
    values = {
        "rn": row["rn"], "rf_kN": row["rf_kN"],
        "cf_ittc1957": R.ittc1957_cf(row["rn"]),
        "pe_kw_at_trial": imp["values"]["pe_kw"],
        "r_total_kN": imp["values"]["r_total_n"] / 1000.,
        "rr_kN": imp["values"]["rr_n"] / 1000.,
        "cr_implied": imp["values"]["cr_implied"],
        "cr_table_normal_estimate": row["cr"], "cr_table_model": mr["cr"],
        "shp_predicted_normal_estimate": row["shp_required"],
        "qpc_implied_by_table_normal_estimate": row["pe_shp"] / shp if row["complete"] else None,
        "qpc_implied_by_table_model": mr["pe_shp"] / shp if mr["complete"] else None,
    }
    case = {
        "schema": "plimsoll-resistance-2", "ship": "HMS Queen Mary (1913)", "estimate": True,
        "_note": "正常载荷主尺度 + 同载荷 Mumford 湿面积 + 假定 Cm；满载模型全套参数单列。"
                 "试航载荷、吨位单位未确认；反解 QPC 只作诊断，不构成历史验证或拟合目标。"
                 "values.r_total_kN/rr_kN 为试航功率在假定 QPC 下的反解；预测见 normal_prediction。",
        "inputs": {"normal_estimate": hp, "model_full_load": model,
                   "trial": trial, "qpc_assumed": qpc},
        "normal_prediction": row, "model_full_load_prediction": mr,
        "values": values,
        "trace": [dict(t, estimate=True, basis="normal_estimate") for t in row["trace"]] +
                 [dict(t, basis="trial_inverse_normal_estimate") for t in imp["trace"]] +
                 [dict(t, estimate=True, basis="model_full_load") for t in mr["trace"]],
        "warnings": normal["warnings"] + imp["warnings"] +
                    ["满载模型对照：" + w for w in comparison["warnings"]],
    }
    OUT.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("written:", OUT)


if __name__ == "__main__":
    main()
