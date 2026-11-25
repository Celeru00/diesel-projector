import re

import pandas as pd
from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from fuelcast.advisor import PERSONAS, signed_peso
from fuelcast.config import ASOF_DAY

console = Console()

MODEL_LABELS = {
    "hybrid": "Hybrid (k-NN + LR)",
    "linreg": "Linear regression",
    "knn": "k-NN",
    "persistence": "Baseline: persistence",
    "majority": "Baseline: majority class",
}
BASELINES = {"persistence", "majority"}

TIMING_LABELS = {
    "buy_before": "Buy before Tuesday",
    "wait": "Wait for the rollback",
    "normal": "Buy as usual",
    "shock_partial_topup": "Partial top-up only (shock)",
    "shock_buy_as_needed": "Buy only as needed (shock)",
}

SCENARIO_LABELS = {
    "baseline": "Actual market (no change)",
    "brent_spike_15": "Brent +15% over 5 days",
    "brent_crash_20": "Brent −20% over 5 days",
    "peso_slide_4": "Peso weakens 4%",
    "diesel_squeeze": "Diesel-only spike (+18%)",
}

CONDITION_LABELS = {
    "all weeks": "All weeks",
    "shock=yes": "Shock weeks",
    "shock=no": "Normal weeks",
    "turning_point=yes": "Direction changed from last week",
    "turning_point=no": "Same direction as last week",
    "near_flat=yes": "Near-flat moves (≤ ₱0.25)",
    "near_flat=no": "Clear moves (> ₱0.25)",
    "large_move=yes": "Large moves (≥ ₱1.50)",
    "large_move=no": "Small or moderate moves",
    "high_confidence=yes": "High-confidence forecasts (≥ 75%)",
    "high_confidence=no": "Lower-confidence forecasts",
    "late_reversal=yes": f"Prices reversed after {ASOF_DAY}",
    "late_reversal=no": "No late reversal",
}

FEATURE_LABELS = {
    "implied_partial": ("Price change so far this week", "₱/L"),
    "bench_trend5_pct": ("Diesel benchmark, 5-day trend", "%"),
    "brent_trend5_pct": ("Brent crude, 5-day trend", "%"),
    "brent_slope5": ("Brent crude, 5-day slope", "$/day"),
    "fx_trend5_pct": ("USD/PHP, 5-day trend", "%"),
    "brent_vol20": ("Brent 20-day volatility", "%/yr"),
    "bench_vs_ma20_pct": ("Diesel vs its 20-day average", "%"),
    "lag1": ("Adjustment 1 week ago", "₱/L"),
    "lag2": ("Adjustment 2 weeks ago", "₱/L"),
    "lag3": ("Adjustment 3 weeks ago", "₱/L"),
}

DIRECTION_STYLE = {"up": ("▲ PRICE HIKE", "bold red"), "down": ("▼ ROLLBACK", "bold green"), "flat": ("■ NO CHANGE", "bold yellow")}


def pct(x: float, digits: int = 1) -> str:
    return "—" if pd.isna(x) else f"{x * 100:.{digits}f}%"


def peso(x: float) -> str:
    return "—" if pd.isna(x) else signed_peso(x)


def signed(x: float, digits: int = 2) -> str:
    return f"{'+' if x > 0 else '−' if x < 0 else '±'}{abs(x):.{digits}f}"


def signed_pct(x: float) -> str:
    return "—" if pd.isna(x) else f"{'+' if x > 0 else '−' if x < 0 else '±'}{abs(x):.1f}%"


def conf_text(c: float) -> str:
    return ">99%" if c >= 0.995 else f"{c * 100:.0f}%"


def pvalue(p: float) -> str:
    return "—" if pd.isna(p) else "< 0.001" if p < 0.001 else f"{p:.3f}"


def date_text(d) -> str:
    return pd.Timestamp(d).strftime("%a, %b %d, %Y").replace(" 0", " ")


def rule_name(name: str) -> str:
    return re.sub(r"-\d+$", "", name)


def section(title: str) -> None:
    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="cyan"))


def table(*columns, title: str | None = None, caption: str | None = None) -> Table:
    t = Table(title=title, caption=caption, box=box.SIMPLE_HEAVY, header_style="bold cyan", title_justify="left", caption_justify="left")
    for col in columns:
        name, justify = col if isinstance(col, tuple) else (col, "left")
        t.add_column(name, justify=justify)
    return t


def show_banner(doe_loaded: bool) -> None:
    console.print(
        Panel(
            Text.assemble(("Diesel Price Adjustment Predictor & Advisor\n", "bold"), ("Weekly Philippine pump price forecast · k-NN + linear regression · rule-based advisor", "dim")),
            border_style="cyan",
            box=box.ROUNDED,
        )
    )
    if not doe_loaded:
        console.print(
            Panel(
                "No official DOE history found ([bold]data/doe_adjustments.csv[/bold]).\n"
                "The model is trained and scored on [bold]estimated[/bold] adjustments computed from market prices, so accuracy figures are optimistic.",
                title="⚠ Data note",
                title_align="left",
                border_style="yellow",
            )
        )


def show_cleaning(report: dict) -> None:
    section("1 · Data ingestion and cleaning")
    names = {"brent": "Brent crude (BZ=F)", "mops_gasoil": "Diesel benchmark (HO=F)", "usdphp": "USD/PHP (PHP=X)"}
    t = table("Series", ("Gaps forward-filled", "right"), ("Bad ticks removed", "right"), caption=f"{report['rows']:,} trading days after cleaning · all prices converted to ₱/L")
    for key, label in names.items():
        if key in report["missing_before_ffill"]:
            t.add_row(label, str(report["missing_before_ffill"][key]), str(report["spikes_removed"][key]))
    console.print(t)


def _metrics_table(m: pd.DataFrame, title: str | None = None) -> Table:
    t = table(
        "Model", ("Direction correct", "right"), ("Precision", "right"), ("Recall", "right"), ("F1", "right"), ("MAE ₱/L", "right"), ("RMSE ₱/L", "right"), ("In 80% range", "right"), title=title
    )
    best = m.loc[~m["model"].isin(BASELINES), "mae"].min()
    for r in m.itertuples(index=False):
        style = "dim" if r.model in BASELINES else "bold green" if r.mae == best else ""
        t.add_row(
            MODEL_LABELS[r.model],
            pct(r.directional_accuracy),
            f"{r.macro_precision:.2f}",
            f"{r.macro_recall:.2f}",
            f"{r.macro_f1:.2f}",
            f"{r.mae:.2f}",
            f"{r.rmse:.2f}",
            pct(r.interval_coverage, 0),
            style=style,
        )
    return t


def show_metrics(metrics: pd.DataFrame) -> None:
    section("2 · Walk-forward evaluation")
    allw = metrics[metrics["subset"] == "all"]
    n = int(allw["n"].iloc[0])
    console.print(f"[dim]Each of the last {n} weeks was predicted using only earlier weeks, as in real use.[/dim]")
    console.print(_metrics_table(allw))
    shock = metrics[metrics["subset"] == "shock"]
    if not shock.empty:
        console.print(_metrics_table(shock, title=f"Shock weeks only ({int(shock['n'].iloc[0])} weeks)"))


def show_baselines(bc: pd.DataFrame) -> None:
    section("3 · Comparison with baselines")
    t = table(
        "Model", "Compared with", ("Direction correct", "right"), ("Error reduction", "right"), ("Weeks with smaller error", "right"), ("p-value (DM / McNemar)", "right"), ("Significant", "center")
    )
    for r in bc.itertuples(index=False):
        mark = "[bold green]✓[/bold green]" if r.significant else "[red]✗[/red]"
        t.add_row(
            MODEL_LABELS[r.model],
            MODEL_LABELS[r.baseline].replace("Baseline: ", ""),
            f"{pct(r.dir_acc_model)} vs {pct(r.dir_acc_baseline)}",
            pct(r.mae_skill, 0),
            pct(r.win_rate, 0),
            f"{pvalue(r.dm_pvalue)} / {pvalue(r.mcnemar_pvalue)}",
            mark,
        )
    console.print(t)
    console.print("[dim]Error reduction = 1 − model MAE ÷ baseline MAE. Diebold–Mariano tests error size; McNemar tests directional hits.[/dim]")


def show_failures(fb: pd.DataFrame, fc: pd.DataFrame, limit: int = 10) -> None:
    section("4 · Where the hybrid model fails")
    t = table("Condition", ("Weeks", "right"), ("Direction correct", "right"), ("Failure rate", "right"), ("MAE ₱/L", "right"))
    rows = fb[fb["model"] == "hybrid"]
    for i, r in enumerate(rows.itertuples(index=False)):
        if i and r.condition.endswith("=yes"):
            t.add_section()
        weak = r.directional_accuracy < 0.8
        t.add_row(
            CONDITION_LABELS.get(r.condition, r.condition),
            str(r.n),
            pct(r.directional_accuracy),
            pct(r.failure_rate),
            f"{r.mae:.2f}",
            style="bold red" if weak else "bold" if r.condition == "all weeks" else "",
        )
    console.print(t)
    console.print("[dim]Failure = wrong direction, or right direction but off by more than max(2 × MAE, ₱0.50). Red rows are below 80% direction accuracy.[/dim]")
    if fc.empty:
        return
    w = table("Week", "Failure", ("Actual", "right"), ("Forecast", "right"), "Likely cause", title=f"Worst {min(limit, len(fc))} failure weeks")
    for r in fc.head(limit).itertuples(index=False):
        w.add_row(pd.Timestamp(r.effective_date).strftime("%Y-%m-%d"), "Wrong direction" if r.failure_type == "wrong_direction" else "Large miss", peso(r.actual), peso(r.pred), r.likely_cause)
    console.print(w)


def show_forecast(fc: pd.DataFrame) -> None:
    section("5 · Forecast")
    r = fc.iloc[0]
    label, style = DIRECTION_STYLE[r["direction"]]
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", justify="right")
    grid.add_column()
    grid.add_row("Effective", f"[bold]{date_text(r['effective_date'])}[/bold], 6:00 AM")
    grid.add_row("Forecast", Text.assemble((f"{label}  ", style), (f"{signed_peso(r['pred'])} per liter", "bold")))
    grid.add_row("80% range", f"{signed_peso(r['low'])} to {signed_peso(r['high'])} per liter")
    agree = "[green]models agree[/green]" if r.get("models_agree", True) else "[yellow]models disagree[/yellow]"
    grid.add_row("Confidence", f"{conf_text(r['confidence'])}  [dim](k-NN {signed_peso(r['knn_pred'])} · linear regression {signed_peso(r['linreg_pred'])} · {agree})[/dim]")
    shock = r["shock_reason"] if isinstance(r["shock_reason"], str) else None
    grid.add_row("Shock check", f"[bold red]{shock}[/bold red]" if shock else f"[green]Normal week[/green] [dim](Brent {signed_pct(r['brent_trend5_pct'])} over 5 days)[/dim]")
    src = "official DOE" if r["target_source"] == "doe" else "estimated"
    grid.add_row("Forecast made", f"{date_text(r['asof'])} (runs every {ASOF_DAY}, one week ahead)")
    grid.add_row("Based on", f"{int(r['n_train'])} past weeks of {src} adjustments")
    console.print(Panel(grid, title="[bold]Diesel · next Tuesday[/bold]", title_align="left", border_style=style.split()[-1], box=box.ROUNDED))


def show_advice(items: list[dict]) -> None:
    section("6 · Advice")
    for a in items:
        console.print(advice_panel(a))


def advice_panel(a: dict) -> Panel:
    facts = a["facts"]
    shock = facts.get("mode") == "shock"
    color = "red" if shock else {"up": "red", "down": "green", "flat": "yellow"}[facts["direction"]]
    body = [Text(a["headline"], style=f"bold {color}"), Text()]
    timing = TIMING_LABELS.get(facts.get("timing"), "")
    if timing:
        body.append(Text.assemble(("Decision: ", "dim"), (timing, "bold")))
    bullets = Table.grid(padding=(0, 1))
    bullets.add_column(width=3, justify="right")
    bullets.add_column()
    for line in a["actions"]:
        bullets.add_row("•", line)
    body.append(bullets)
    body += [Text(), Text("Reasoning: " + " → ".join(rule_name(x) for x in a["trace"]), style="dim")]
    label = PERSONAS[a["persona"]]["label"]
    vol = facts.get("liters_per_week", PERSONAS[a["persona"]]["liters_per_week"])
    return Panel(Group(*body), title=f"[bold]{label}[/bold] [dim]· {vol:,.0f} L/week[/dim]", title_align="left", border_style=color, box=box.ROUNDED)


def show_stress(df: pd.DataFrame) -> None:
    section("7 · Shock stress tests")
    console.print("[dim]Each scenario distorts the last 5 trading days of real data and re-runs the whole pipeline.[/dim]")
    t = table("Scenario", ("Brent 5-day", "right"), ("Forecast", "right"), ("80% range", "right"), "Shock detected", "Fleet decision")
    for r in df.itertuples(index=False):
        shock = "[bold red]Yes[/bold red]" if r.shock else "[dim]No[/dim]"
        t.add_row(SCENARIO_LABELS.get(r.scenario, r.scenario), signed_pct(r.brent_trend5_pct), peso(r.pred), f"{peso(r.low)} to {peso(r.high)}", shock, TIMING_LABELS.get(r.timing, r.timing))
    console.print(t)


def show_saved(paths: list[str]) -> None:
    console.print()
    for p in paths:
        console.print(f"[dim]Saved[/dim] {p}")


def show_explain(e: dict) -> None:
    console.print(Panel(f"Why the model forecasts [bold]{signed_peso(e['pred'])}/L[/bold] for {date_text(e['effective_date'])}", border_style="cyan", box=box.ROUNDED))
    section("How the two techniques are blended")
    w = e["knn_weight"]
    t = table("Technique", ("Forecast", "right"), ("Weight", "right"), ("Contribution", "right"))
    t.add_row("k-NN (similar past weeks)", peso(e["knn_pred"]), pct(w, 0), peso(w * e["knn_pred"]))
    t.add_row("Linear regression", peso(e["linreg_pred"]), pct(1 - w, 0), peso((1 - w) * e["linreg_pred"]))
    t.add_section()
    t.add_row("[bold]Hybrid forecast[/bold]", f"[bold]{peso(e['pred'])}[/bold]", "100%", "")
    console.print(t)
    console.print("[dim]Weights are learned from each technique's error on the last 26 training weeks (lower error → higher weight).[/dim]")

    section(f"Conditions when the forecast was made ({date_text(e['asof'])})")
    c = table("Feature", ("Value", "right"), "Unit")
    for k, v in e["current"].items():
        name, unit = FEATURE_LABELS.get(k, (k, ""))
        c.add_row(name, f"{v:.2f}" if k == "brent_vol20" else signed(v), unit)
    console.print(c)

    section(f"k-NN: the {len(e['neighbors'])} most similar past weeks")
    n = table("Week", ("Distance", "right"), ("Change so far", "right"), ("Brent 5-day", "right"), ("Previous week", "right"), ("Actual adjustment", "right"))
    for r in e["neighbors"].itertuples(index=False):
        n.add_row(
            r.week, f"{r.distance:.2f}", peso(r.implied_partial), signed_pct(r.brent_trend5_pct), peso(r.lag1), Text(peso(r.target), style="green" if r.target < 0 else "red" if r.target > 0 else "")
        )
    console.print(n)
    console.print("[dim]Distance is measured on standardized features; closer weeks count more.[/dim]")

    section("Linear regression: what moves the forecast")
    coefs = e["coefficients"]
    top = coefs.abs().max() or 1
    r = table("Feature", ("Weight", "right"), "")
    for k, v in coefs.items():
        bar = "█" * max(1, round(abs(v) / top * 24))
        r.add_row(FEATURE_LABELS.get(k, (k,))[0], signed(v, 3), Text(bar, style="green" if v > 0 else "red"))
    console.print(r)
    console.print("[dim]Standardized coefficients: change in forecast (₱/L) for a one-standard-deviation change in the feature.[/dim]")
