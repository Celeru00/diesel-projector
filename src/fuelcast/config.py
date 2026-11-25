from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "fuelcast.db"
DOE_CSV = DATA_DIR / "doe_adjustments.csv"
REPORT_DIR = ROOT / "reports"

FUEL = "diesel"
FUELS = (FUEL,)

MARKET_SYMBOLS = {
    "brent": "BZ=F",
    "mops_gasoil": "HO=F",
    "usdphp": "PHP=X",
}

FUEL_BENCHMARK = {
    "diesel": "mops_gasoil",
}

LITERS_PER_BARREL = 158.987
LITERS_PER_GALLON = 3.78541
VAT = 1.12
ADJUSTMENT_TICK = 0.05
FLAT_BAND = 0.10


@dataclass(frozen=True)
class Settings:
    start: str = "2018-01-01"
    asof_weekday: int = 1
    min_train_weeks: int = 104
    knn_k: int = 7
    lags: int = 3
    shock_brent_pct: float = 8.0
    shock_vol_z: float = 2.5
    outlier_z: float = 6.0
    fuels: tuple[str, ...] = field(default=FUELS)


SETTINGS = Settings()
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
ASOF_DAY = WEEKDAYS[SETTINGS.asof_weekday]
