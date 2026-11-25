from collections.abc import Callable
from dataclasses import dataclass, field

PERSONAS = {
    "motorist": {"label": "Private motorist", "fuel": "diesel", "liters_per_week": 40.0},
    "tricycle": {"label": "Tricycle operator", "fuel": "diesel", "liters_per_week": 25.0},
    "fleet": {"label": "Fleet / logistics operator", "fuel": "diesel", "liters_per_week": 5000.0},
}

CONF_HIGH = 0.75
CONF_MED = 0.55
SIZE_SMALL = 0.50
SIZE_LARGE = 1.50


@dataclass
class Rule:
    name: str
    salience: int
    when: Callable[[dict], bool]
    then: Callable[[dict], None]


@dataclass
class Advice:
    persona: str
    fuel: str
    headline: str
    actions: list[str]
    facts: dict
    trace: list[str] = field(default_factory=list)


def _add(wm: dict, key: str, text: str) -> None:
    wm.setdefault(key, [])
    if text not in wm[key]:
        wm[key].append(text)


def _peso(x: float) -> str:
    return f"₱{abs(x):,.2f}"


def _set(**kv):
    def act(wm):
        wm.update(kv)

    return act


def _lower_conf(wm):
    wm["confidence_level"] = {"high": "medium", "medium": "low", "low": "low"}[wm["confidence_level"]]
    wm["conf_downgraded"] = True
    _add(wm, "notes", "k-NN and linear regression disagree on direction, so confidence was lowered one step.")


def _shock_mode(wm):
    wm["mode"] = "shock"
    _add(wm, "notes", f"Shock week detected ({wm['shock_reason']}). Market moves may outrun the model.")
    wm["low"] = min(wm["low"], wm["pred"] - abs(wm["pred"]) * 0.5 - 0.5)
    wm["high"] = max(wm["high"], wm["pred"] + abs(wm["pred"]) * 0.5 + 0.5)


def _impact(wm):
    liters = wm["liters_per_week"]
    wm["weekly_impact"] = wm["pred"] * liters
    wm["weekly_impact_high"] = max(abs(wm["low"]), abs(wm["high"])) * liters


BASE_RULES = [
    Rule("classify-confidence-high", 100, lambda f: "confidence_level" not in f and f["confidence"] >= CONF_HIGH, _set(confidence_level="high")),
    Rule("classify-confidence-medium", 100, lambda f: "confidence_level" not in f and CONF_MED <= f["confidence"] < CONF_HIGH, _set(confidence_level="medium")),
    Rule("classify-confidence-low", 100, lambda f: "confidence_level" not in f and f["confidence"] < CONF_MED, _set(confidence_level="low")),
    Rule("classify-size-small", 100, lambda f: abs(f["pred"]) < SIZE_SMALL, _set(size="small")),
    Rule("classify-size-moderate", 100, lambda f: SIZE_SMALL <= abs(f["pred"]) < SIZE_LARGE, _set(size="moderate")),
    Rule("classify-size-large", 100, lambda f: abs(f["pred"]) >= SIZE_LARGE, _set(size="large")),
    Rule("model-disagreement", 95, lambda f: "confidence_level" in f and f.get("models_agree") is False and not f.get("conf_downgraded"), _lower_conf),
    Rule("shock-override", 90, lambda f: f.get("shock") and f.get("mode") != "shock", _shock_mode),
    Rule("compute-impact", 80, lambda f: "size" in f and "weekly_impact" not in f, _impact),
    Rule("signal-strong", 70, lambda f: f.get("confidence_level") in ("high", "medium") and f["direction"] != "flat" and "signal" not in f, _set(signal="strong")),
    Rule("signal-weak", 70, lambda f: "signal" not in f and (f.get("confidence_level") == "low" or f["direction"] == "flat"), _set(signal="weak")),
    Rule("timing-buy-before", 60, lambda f: f.get("signal") == "strong" and f["direction"] == "up" and f.get("mode") != "shock", _set(timing="buy_before")),
    Rule("timing-wait", 60, lambda f: f.get("signal") == "strong" and f["direction"] == "down" and f.get("mode") != "shock", _set(timing="wait")),
    Rule("timing-normal", 60, lambda f: f.get("signal") == "weak" and f.get("mode") != "shock", _set(timing="normal")),
    Rule("timing-shock-up", 60, lambda f: f.get("mode") == "shock" and f["direction"] in ("up", "flat") and "signal" in f, _set(timing="shock_partial_topup")),
    Rule("timing-shock-down", 60, lambda f: f.get("mode") == "shock" and f["direction"] == "down" and "signal" in f, _set(timing="shock_buy_as_needed")),
]


def signed_peso(x: float) -> str:
    sign = "+" if x > 0 else "−" if x < 0 else "±"
    return f"{sign}₱{abs(x):.2f}"


def _headline(wm):
    fuel = wm["fuel"].capitalize()
    rng = f"{signed_peso(wm['low'])} to {signed_peso(wm['high'])}"
    word = {"up": "price hike", "down": "rollback", "flat": "little to no change"}[wm["direction"]]
    conf = f"{wm['confidence_level']} confidence"
    if wm["direction"] == "flat":
        core = f"{fuel}: {word} expected ({signed_peso(wm['pred'])}/L; range {rng}; {conf})"
    else:
        core = f"{fuel}: {word} of about {signed_peso(wm['pred'])}/L expected (range {rng}; {conf})"
    wm["headline"] = ("[SHOCK WEEK] " if wm.get("mode") == "shock" else "") + core


def _r(persona, timing, text_fn, salience=40, extra=lambda f: True):
    def when(f):
        return f["persona"] == persona and f.get("timing") == timing and extra(f)

    def then(f):
        _add(f, "actions", text_fn(f))

    return Rule(f"{persona}-{timing}-{salience}", salience, when, then)


PERSONA_RULES = [
    _r("motorist", "buy_before", lambda f: f"Fill up before Tuesday 6:00 AM. A full {f['liters_per_week']:.0f} L of fuel will cost about {_peso(f['weekly_impact'])} more after the hike."),
    _r("motorist", "wait", lambda f: f"If your tank allows, wait until Tuesday to refuel and save about {_peso(f['weekly_impact'])} on {f['liters_per_week']:.0f} L."),
    _r("motorist", "normal", lambda f: "No strong signal. Refuel as you normally would; timing your fill-up won't save much this week."),
    _r("motorist", "shock_partial_topup", lambda f: "Top up only what you need for the coming days. Prices are volatile, so don't panic-buy or hoard in containers."),
    _r("motorist", "shock_buy_as_needed", lambda f: "A rollback is likely but markets are volatile. Buy only what you need and check the DOE announcement on Monday."),
    _r("tricycle", "buy_before", lambda f: f"Refuel before Tuesday. Set aside about {_peso(f['weekly_impact'])} extra for this week's fuel ({f['liters_per_week']:.0f} L)."),
    _r("tricycle", "wait", lambda f: f"Refuel daily as usual and skip a full tank on Monday. The rollback saves about {_peso(f['weekly_impact'])} a week."),
    _r("tricycle", "normal", lambda f: "Keep your usual daily refuelling routine. The expected change to your weekly budget is small."),
    _r("tricycle", "shock_partial_topup", lambda f: f"Keep a buffer of up to {_peso(f['weekly_impact_high'])} this week. Check whether you qualify for LTFRB/DOTr fuel subsidy programs."),
    _r("tricycle", "shock_buy_as_needed", lambda f: "Buy fuel daily as needed. Prices may swing either way this week."),
    _r("fleet", "buy_before", lambda f: f"Top up depot and vehicle tanks before Tuesday. Weekly cost exposure is about {_peso(f['weekly_impact'])} on {f['liters_per_week']:,.0f} L."),
    _r("fleet", "wait", lambda f: f"Defer bulk purchases until after Tuesday's rollback to save about {_peso(f['weekly_impact'])} on {f['liters_per_week']:,.0f} L."),
    _r("fleet", "normal", lambda f: "Keep the standard purchasing schedule. Expected weekly cost change is within normal tolerance."),
    _r(
        "fleet",
        "shock_partial_topup",
        lambda f: f"Split purchases: buy about half your weekly volume now and the rest after the announcement. Worst-case exposure is about {_peso(f['weekly_impact_high'])}.",
    ),
    _r("fleet", "shock_buy_as_needed", lambda f: "Buy for immediate needs only, and re-quote suppliers after the Monday announcement."),
    _r("fleet", "buy_before", lambda f: "This is a large hike: check fuel-surcharge clauses in client contracts and update delivery quotes.", 35, lambda f: f.get("size") == "large"),
    Rule(
        "fleet-shock-surcharge",
        35,
        lambda f: f["persona"] == "fleet" and f.get("mode") == "shock",
        lambda f: _add(f, "actions", "Turn on fuel-surcharge or price-escalation clauses, and review routes to cut idle and empty-run fuel."),
    ),
    Rule("all-low-confidence", 30, lambda f: f.get("confidence_level") == "low", lambda f: _add(f, "notes", "Low confidence: the forecast range crosses zero or past similar weeks were mixed.")),
    Rule(
        "all-large-move",
        30,
        lambda f: f.get("size") == "large" and f.get("mode") != "shock",
        lambda f: _add(f, "notes", "This is a large move compared with typical weekly adjustments (usually under ₱1.50/L)."),
    ),
    Rule("emit-headline", 10, lambda f: "headline" not in f and "timing" in f, _headline),
]

RULES = sorted(BASE_RULES + PERSONA_RULES, key=lambda r: -r.salience)


def infer(facts: dict, rules: list[Rule] = RULES, max_cycles: int = 200) -> tuple[dict, list[str]]:
    wm = dict(facts)
    fired: set[str] = set()
    trace = []
    for _ in range(max_cycles):
        agenda = [r for r in rules if r.name not in fired and r.when(wm)]
        if not agenda:
            break
        rule = agenda[0]
        rule.then(wm)
        fired.add(rule.name)
        trace.append(rule.name)
    return wm, trace


def detect_shock(brent_trend5_pct: float, brent_vol_z: float, pct_threshold: float, z_threshold: float) -> str | None:
    reasons = []
    if abs(brent_trend5_pct) >= pct_threshold:
        reasons.append(f"Brent moved {brent_trend5_pct:+.1f}% in 5 days".replace("-", "−"))
    if brent_vol_z == brent_vol_z and brent_vol_z >= z_threshold:
        reasons.append(f"volatility z-score {brent_vol_z:.1f}")
    return "; ".join(reasons) or None


def advise(prediction: dict, persona: str, fuel: str | None = None, liters_per_week: float | None = None, shock_reason: str | None = None) -> Advice:
    if persona not in PERSONAS:
        raise ValueError(f"Unknown persona {persona!r}; choose from {sorted(PERSONAS)}")
    p = PERSONAS[persona]
    facts = {
        "persona": persona,
        "fuel": fuel or p["fuel"],
        "liters_per_week": liters_per_week or p["liters_per_week"],
        "pred": float(prediction["pred"]),
        "low": float(prediction["low"]),
        "high": float(prediction["high"]),
        "direction": prediction["direction"],
        "confidence": float(prediction["confidence"]),
        "models_agree": prediction.get("models_agree"),
        "shock": bool(shock_reason),
        "shock_reason": shock_reason,
    }
    wm, trace = infer(facts)
    return Advice(
        persona=persona,
        fuel=wm["fuel"],
        headline=wm.get("headline", ""),
        actions=wm.get("actions", []) + wm.get("notes", []),
        facts={k: v for k, v in wm.items() if k not in ("actions", "notes", "headline")},
        trace=trace,
    )
