import logging
import pandas as pd
from src.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

EXPECTED_COLS = {
  "unique_key",
  "agency",
  "agency_name",
  "complaint_type",
  "descriptor",
  "incident_zip",
  "incident_address",
  "street_name",
  "address_type",
  "city",
  "police_precinct",
  "borough",
  "latitude",
  "longitude",
  "status",
  "resolution_description",
  "created_date",
  "resolution_action_updated_date",
  "landmark",
  "facility_type",
  "park_facility_name",
  "park_borough",
}

def validate_schema(df : pd.DataFrame) -> None:
  """_summary_
  """
  missing_cols = EXPECTED_COLS - set(df.columns)

  if missing_cols:
    raise ValueError(f"Missing expected column(s): {sorted(missing_cols)}")