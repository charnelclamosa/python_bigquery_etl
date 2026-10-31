import json
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

STATE_PATH = Path("data/state.json")
LOOKBACK_DAYS = 14
TS_FORMAT = "%Y-%m-%dT%H:%M:%S.000"


def fmt_ts(ts: datetime) -> str:
  return ts.strftime(TS_FORMAT)


def load_watermark() -> str:
  """
  Last successfully loaded created_date, or now minus the lookback.
  """
  if STATE_PATH.exists():
    return json.loads(STATE_PATH.read_text())["last_created_date"]
  
  return fmt_ts(datetime.now() - timedelta(days=LOOKBACK_DAYS))


def save_watermark(value: str) -> None:
  """
  Call only after the load step succeeds.
  """
  STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
  STATE_PATH.write_text(json.dumps({"last_created_date": value}))


def to_records(df: pd.DataFrame) -> list[dict]:
  """
  DataFrame to list of dicts, with NaN/NaT converted to None.
  """
  return df.astype(object).where(df.notna(), None).to_dict("records")