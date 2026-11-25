from datetime import datetime

import pandas as pd

from fuelcast.config import ASOF_DAY, REPORT_DIR
from fuelcast.domain.advisor import PERSONAS, signed_peso
from fuelcast.interface.display import (
    BASELINES,
    CONDITION_LABELS,
    DIRECTION_STYLE,
    MODEL_LABELS,
    SCENARIO_LABELS,
    TIMING_LABELS,
    conf_text,
    date_text,
    pct,
    peso,
    pvalue,
    rule_name,
    signed_pct,
)


def _md(headers: list[str], rows: list[list], align: str | None = None) -> str:
    align = align or "l" * len(headers)
    sep = ["---:" if a == "r" else ":---:" if a == "c" else "---" for a in align]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(sep) + " |"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def _source_note(doe_loaded: bool) -> list[str]:
    if doe_loaded:
        return ["> Trained and scored on **official DOE adjustments** (`data/doe_adjustments.csv`).", ""]
    return [
        "> ⚠ **Data note:** no official DOE history was supplied. The model is trained and scored on **estimated** adjustments computed from market prices, so accuracy figures are optimistic.",
        "",
    ]


def _metrics(m: pd.DataFrame) -> str:
    rows = []
    best = m.loc[~m["model"].isin(BASELINES), "mae"].min()
    for r in m.itertuples(index=False):
        name = MODEL_LABELS[r.model]
        name = f"**{name}**" if r.mae == best and r.model not in BASELINES else name
        rows.append([name, pct(r.directional_accuracy), f"{r.macro_precision:.2f}", f"{r.macro_recall:.2f}", f"{r.macro_f1:.2f}", f"{r.mae:.2f}", f"{r.rmse:.2f}", pct(r.interval_coverage, 0)])
    return _md(["Model", "Direction correct", "Precision", "Recall", "F1", "MAE (₱/L)", "RMSE (₱/L)", "In 80% range"], rows, "lrrrrrrr")


def evaluation_sections(metrics: pd.DataFrame, analysis: dict) -> list[str]:
    allw = metrics[metrics["subset"] == "all"]
    shock = metrics[metrics["subset"] == "shock"]
    lines = ["## Walk-forward evaluation", "", f"Each of the last {int(allw['n'].iloc[0])} weeks was predicted using only earlier weeks.", "", _metrics(allw), ""]
    if not shock.empty:
        lines += [f"### Shock weeks only ({int(shock['n'].iloc[0])} weeks)", "", _metrics(shock), ""]

    bc = analysis["baseline_comparison"]
    rows = [
        [
            MODEL_LABELS[r.model],
            MODEL_LABELS[r.baseline].replace("Baseline: ", ""),
            f"{pct(r.dir_acc_model)} vs {pct(r.dir_acc_baseline)}",
            pct(r.mae_skill, 0),
            pct(r.win_rate, 0),
            pvalue(r.dm_pvalue),
            pvalue(r.mcnemar_pvalue),
            "✓" if r.significant else "✗",
        ]
        for r in bc.itertuples(index=False)
    ]
    lines += [
        "## Comparison with baselines",
        "",
        _md(["Model", "Compared with", "Direction correct", "Error reduction", "Weeks with smaller error", "Diebold–Mariano p", "McNemar p", "Significant"], rows, "llrrrrrc"),
        "",
        "Error reduction = 1 − model MAE ÷ baseline MAE. Diebold–Mariano tests whether error sizes differ; McNemar tests whether directional hits differ (p < 0.05 = significant).",
        "",
    ]

    fb = analysis["failure_breakdown"]
    fb = fb[fb["model"] == "hybrid"]
    rows = [[CONDITION_LABELS.get(r.condition, r.condition), r.n, pct(r.directional_accuracy), pct(r.failure_rate), f"{r.mae:.2f}"] for r in fb.itertuples(index=False)]
    lines += [
        "## Where the hybrid model fails",
        "",
        "A failure is a wrong direction, or the right direction but an error above max(2 × MAE, ₱0.50).",
        "",
        _md(["Condition", "Weeks", "Direction correct", "Failure rate", "MAE (₱/L)"], rows, "lrrrr"),
        "",
    ]
    fc = analysis["failure_cases"]
    if not fc.empty:
        rows = [
            [
                pd.Timestamp(r.effective_date).strftime("%Y-%m-%d"),
                "Wrong direction" if r.failure_type == "wrong_direction" else "Large miss",
                peso(r.actual),
                peso(r.pred),
                conf_text(r.confidence),
                r.likely_cause,
            ]
            for r in fc.itertuples(index=False)
        ]
        lines += ["### Worst failure weeks", "", _md(["Week", "Failure", "Actual", "Forecast", "Confidence", "Likely cause"], rows, "llrrrl"), ""]
    return lines


def write_evaluation_report(res: dict) -> str:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["# Diesel Forecast Evaluation", "", f"_Generated {datetime.now():%B %d, %Y %H:%M}_", ""]
    lines += _source_note(res["doe_loaded"])
    lines += evaluation_sections(res["metrics"], res["analysis"])
    path = REPORT_DIR / "evaluation.md"
    path.write_text("\n".join(lines))
    return str(path)


def write_report(res: dict) -> str:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    fc = res["forecasts"].iloc[0]
    label = DIRECTION_STYLE[fc["direction"]][0]
    lines = [f"# Diesel Price Adjustment Forecast — {date_text(fc['effective_date'])}", "", f"_Generated {datetime.now():%B %d, %Y %H:%M}_", ""]
    lines += _source_note(res["doe_loaded"])

    shock = fc["shock_reason"] if isinstance(fc["shock_reason"], str) else None
    lines += [
        "## Forecast",
        "",
        _md(
            ["", ""],
            [
                ["Effective", f"{date_text(fc['effective_date'])}, 6:00 AM"],
                ["Forecast", f"**{label} {signed_peso(fc['pred'])} per liter**"],
                ["80% range", f"{signed_peso(fc['low'])} to {signed_peso(fc['high'])} per liter"],
                ["Confidence", conf_text(fc["confidence"])],
                ["k-NN / linear regression", f"{signed_peso(fc['knn_pred'])} / {signed_peso(fc['linreg_pred'])} ({'agree' if fc['models_agree'] else 'disagree'})"],
                ["Shock check", f"**{shock}**" if shock else f"Normal week (Brent {signed_pct(fc['brent_trend5_pct'])} over 5 days)"],
                ["Forecast made", f"{date_text(fc['asof'])} (runs every {ASOF_DAY}, one week ahead)"],
                ["Based on", f"{int(fc['n_train'])} past weeks"],
            ],
        ),
        "",
        "## Advice",
        "",
    ]
    for a in res["advice"]:
        p = PERSONAS[a["persona"]]
        lines += [f"### {p['label']} ({a['facts']['liters_per_week']:,.0f} L/week)", "", f"**{a['headline']}**", ""]
        timing = TIMING_LABELS.get(a["facts"].get("timing"))
        if timing:
            lines += [f"Decision: **{timing}**", ""]
        lines += [f"- {x}" for x in a["actions"]]
        lines += ["", f"<sub>Reasoning: {' → '.join(rule_name(x) for x in a['trace'])}</sub>", ""]

    cr = res["clean_report"]
    names = {"brent": "Brent crude (BZ=F)", "mops_gasoil": "Diesel benchmark (HO=F)", "usdphp": "USD/PHP (PHP=X)"}
    rows = [[v, cr["missing_before_ffill"][k], cr["spikes_removed"][k]] for k, v in names.items() if k in cr["missing_before_ffill"]]
    lines += ["## Data cleaning", "", f"{cr['rows']:,} trading days after cleaning; all prices converted to ₱/L.", "", _md(["Series", "Gaps forward-filled", "Bad ticks removed"], rows, "lrr"), ""]

    if res["metrics"] is not None:
        lines += evaluation_sections(res["metrics"], res["analysis"])

    if res["stress"] is not None:
        rows = [
            [SCENARIO_LABELS.get(r.scenario, r.scenario), signed_pct(r.brent_trend5_pct), peso(r.pred), f"{peso(r.low)} to {peso(r.high)}", r.shock or "No", TIMING_LABELS.get(r.timing, r.timing)]
            for r in res["stress"].itertuples(index=False)
        ]
        lines += [
            "## Shock stress tests",
            "",
            "Each scenario distorts the last 5 trading days of real data and re-runs the whole pipeline.",
            "",
            _md(["Scenario", "Brent 5-day", "Forecast", "80% range", "Shock detected", "Fleet decision"], rows, "lrrrll"),
            "",
        ]
    path = REPORT_DIR / "report.md"
    path.write_text("\n".join(lines))
    return str(path)
