import os
import pandas as pd
from sodapy import Socrata


DATASET_COLS = [
  # Fact table
  "unique_key",

  # dim_agency
  "agency",
  "agency_name",

  # dim_complaint_type
  "complaint_type",
  "descriptor",

  # dim_location
  "incident_zip",
  "incident_address",
  "street_name",
  "address_type",
  "landmark",
  "city",
  "police_precinct",
  "borough",
  "latitude",
  "longitude",

  # dim_facility
  "facility_type",
  "park_facility_name",
  "park_borough",

  # dim_status
  "status",

  # dim_resolution
  "resolution_description",

  # dim_date
  "created_date",
  "resolution_action_updated_date",
]

def init_client():
  """_summary_
  """
  client = Socrata(
    "data.cityofnewyork.us", 
    os.getenv("NYC_OPEN_DATA_TOKEN"), 
    username=os.getenv("NYC_OPEN_DATA_EMAIL"), 
    password=os.getenv("NYC_OPEN_DATA_PASSWORD"))

  return client


def extract_service_requests(limit=100, offset=0):
  """_summary_

  Available keys:
  https://dev.socrata.com/foundry/data.cityofnewyork.us/erm2-nwe9
  """
  client = init_client()

  try:
    raw = client.get(
      "erm2-nwe9", 
      select=",".join(DATASET_COLS),
      order="created_date DESC",
      limit=limit,
      offset=offset)
    df = pd.DataFrame.from_records(raw)
    df.to_csv("data/data.csv", index=False)
    records = (
      df.astype(object)
        .where(pd.notna(df), None)
        .to_dict(orient="records")
    )
    return records
  except:
    print("Error extracting data")
  finally:
    client.close()

  
  
