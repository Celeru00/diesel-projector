import argparse
from dataclasses import asdict

from fuelcast.application import pipeline
from fuelcast.application.explain import explain
from fuelcast.config import FUEL
from fuelcast.domain.advisor import PERSONAS, advise
from fuelcast.interface import display
from fuelcast.interface.report import write_evaluation_report, write_report


def _show_analysis(res: dict) -> None:
    display.show_metrics(res["metrics"])
    a = res["analysis"]
    display.show_baselines(a["baseline_comparison"])
    display.show_failures(a["failure_breakdown"], a["failure_cases"])


def cmd_run(args) -> None:
    with display.console.status("Running pipeline: ingest → clean → features → evaluate → forecast → advise → stress test…"):
        res = pipeline.run_all(offline=args.offline, shock_override=args.shock, evaluate=not args.skip_eval, stress=not args.skip_stress)
    display.show_banner(res["doe_loaded"])
    display.show_cleaning(res["clean_report"])
    if res["metrics"] is not None:
        _show_analysis(res)
    display.show_forecast(res["forecasts"])
    display.show_advice(res["advice"])
    if res["stress"] is not None:
        display.show_stress(res["stress"])
    display.show_saved([write_report(res), "data/fuelcast.db"])


def cmd_evaluate(args) -> None:
    with display.console.status("Running walk-forward evaluation…"):
        res = pipeline.run_evaluation(offline=args.offline)
    display.show_banner(res["doe_loaded"])
    _show_analysis(res)
    display.show_saved([write_evaluation_report(res)])


def cmd_explain(args) -> None:
    display.show_explain(explain(FUEL))


def cmd_advise(args) -> None:
    pred = {
        "pred": args.pred,
        "low": args.low if args.low is not None else args.pred - 0.5,
        "high": args.high if args.high is not None else args.pred + 0.5,
        "confidence": args.confidence,
        "direction": "up" if args.pred > 0.05 else "down" if args.pred < -0.05 else "flat",
    }
    a = advise(pred, args.persona, liters_per_week=args.liters, shock_reason=args.shock)
    display.console.print(display.advice_panel(asdict(a)))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="fuelcast", description="Weekly Philippine diesel price adjustment predictor and advisor")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="Run the full pipeline: ingest → clean → features → evaluate → forecast → advise → stress test")
    r.add_argument("--offline", action="store_true", help="Use cached market data instead of fetching")
    r.add_argument("--shock", help="Force the geopolitical shock override with this reason")
    r.add_argument("--skip-eval", action="store_true")
    r.add_argument("--skip-stress", action="store_true")
    r.set_defaults(func=cmd_run)
    e = sub.add_parser("evaluate", help="Walk-forward evaluation, baseline comparison, and failure analysis only")
    e.add_argument("--offline", action="store_true", help="Use cached market data instead of fetching")
    e.set_defaults(func=cmd_evaluate)
    x = sub.add_parser("explain", help="Show the similar past weeks and regression weights behind the latest forecast")
    x.set_defaults(func=cmd_explain)
    a = sub.add_parser("advise", help="Run the expert system on a manual prediction")
    a.add_argument("--persona", choices=sorted(PERSONAS), required=True)
    a.add_argument("--pred", type=float, required=True, help="Predicted adjustment in ₱/L")
    a.add_argument("--low", type=float)
    a.add_argument("--high", type=float)
    a.add_argument("--confidence", type=float, default=0.8)
    a.add_argument("--liters", type=float, help="Weekly diesel use in liters")
    a.add_argument("--shock", help="Force the shock override with this reason")
    a.set_defaults(func=cmd_advise)
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
