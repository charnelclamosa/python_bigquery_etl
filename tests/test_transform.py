
import numpy as np
import pandas as pd
import pytest
from src.transform import clean_strings

@pytest.fixture
def nyc_311_df() -> pd.DataFrame:
  return pd.DataFrame(
    {
      "unique_key": [70838962, 70838963, 70838964],
      "agency": ["NYPD", "NYPD ", "DOHMH"],
      "agency_name": [
        "New York City Police Department",
        "  New York City Police Department",
        "Department of Health and Mental Hygiene  ",
      ],
      "complaint_type": ["Noise - Residential", "Noise - Residential", "Rodent"],
      "descriptor": ["Loud Music/Party", "", "   "],
      "incident_zip": [10036.0, 10001.0, np.nan],
      "incident_address": ["605 West  42 Street", " 12 Main St ", None],
      "borough": ["MANHATTAN", "Manhattan ", "BROOKLYN"],
      "latitude": [40.76096011122231, 40.75, np.nan],
      "longitude": [-73.99861746470174, -73.99, np.nan],
      "park_facility_name": ["Unspecified", "Unspecified", " "],
      "status": ["Closed", "Open", "Closed"],
      "created_date": ["2026-10-22 00:25:53", " 2026-10-22 01:00:00", ""],
      "facility_type": [np.nan, np.nan, np.nan],
    },
    index=[100, 200, 300],
  )

def test_remove_leading_spaces(nyc_311_df):
  """_summary_
  """
  expected_agency_name = "New York City Police Department"
  expected_incident_address = "12 Main St"

  actual = clean_strings(nyc_311_df)

  print(actual.loc[200, 'agency_name'])
  assert expected_agency_name == actual.loc[200, 'agency_name']
  assert expected_incident_address == actual.loc[200, 'incident_address']



