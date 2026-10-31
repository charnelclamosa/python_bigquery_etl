import os
import logging
import time
from contextlib import closing
from datetime import datetime
from typing import Iterator
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
from sodapy import Socrata
from src.logging_config import configure_logging
from src.utils import fmt_ts, load_watermark, to_records

configure_logging()
logger = logging.getLogger(__name__)


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
DATASET_ID = "erm2-nwe9"
PAGE_SIZE = 10_000


def init_client():
  """
  Initialize the NYC Open Data Socrata client.

  Returns
  -------
  client : Socrata()
    Initialized connection.
  """
  retry = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
  )
  
  client = Socrata(
    "data.cityofnewyork.us", 
    os.getenv("NYC_OPEN_DATA_TOKEN"), 
    username=os.getenv("NYC_OPEN_DATA_EMAIL"), 
    password=os.getenv("NYC_OPEN_DATA_PASSWORD"),
    timeout=30,
    session_adapter={
      "prefix": "https://",
      "adapter": HTTPAdapter(max_retries=retry),
    })

  return client

def _pages(client, start, end, page_size):
  """
  Lazily fetch service requests one page at a time.

  Parameters
  ----------
  client : Socrata
    Open client, which must stay open until the generator is exhausted.
  start : str
    Window start (inclusive), e.g. "2026-10-01T00:00:00.000".
  end : str
    Window end (exclusive), same format as start.
  page_size : int
    Rows per request.

  Yields
  ------
  batch : list of dict
    Rows of one page, with the columns listed in DATASET_COLS.
  """
  where = f"created_date >= '{start}' AND created_date < '{end}'"
  offset = 0
  page_no = 0

  while batch := client.get(
    DATASET_ID,
    select=",".join(DATASET_COLS),
    where=where,
    order="created_date ASC, unique_key ASC",
    limit=page_size,
    offset=offset
  ):
    page_no += 1
    logger.info("Page %d: %d rows (offset=%d)", page_no, len(batch), offset)
    yield batch

    if len(batch) < page_size:
      return
    
    offset += page_size


def extract_service_requests(start=None, end=None, page_size=PAGE_SIZE):
  """
  Extract NYC 311 service requests created within a time window.

  Fetches all rows with start <= created_date < end, removes duplicate
  rows by unique_key, and returns them with the watermark to save once
  the load succeeds. This function does not save the watermark itself.

  Parameters
  ----------
  start : str, optional
    Window start (inclusive), e.g. "2026-10-01T00:00:00.000".
  end : str, optional
    Window end (exclusive), same format as start.
  page_size : int, optional
    Maximum number of rows per request. Defaults to PAGE_SIZE.

  Returns
  -------
  records : list of dict
    Extracted rows, with missing values as None. Empty if the window has no rows.
  watermark : str
    Maximum created_date among the records, or `start` if there are none.

  Notes
  -----
  The row at the watermark is pulled again on every run, so the load
  must be an upsert on unique_key.

  Available fields:
  https://dev.socrata.com/foundry/data.cityofnewyork.us/erm2-nwe9
  """
  if start is None:
    start = load_watermark()
  if end is None:
    end = fmt_ts(datetime.now())
  t0 = time.perf_counter()

  logger.info("Extraction started: [%s, %s), page_size=%d", 
    start, end, page_size)

  try:
    with closing(init_client()) as client:
      rows = [ 
        row 
        for page in _pages(client, start, end, page_size) 
        for row in page ]
  except:
    logger.exception("Extraction failed for [%s, %s)", start, end)
    raise

  if not rows:
    logger.info("No new records in [%s, %s]", start, end)
    return [], start

  # Later, create separate functions for data cleaning
  df = pd.DataFrame.from_records(rows).drop_duplicates("unique_key")
  dupes = len(rows) - len(df)
  if dupes:
    logger.warning("Dropped %d duplicate rows by unique_key", dupes)

  records = to_records(df)

  new_wm = df["created_date"].max()

  logger.info(
    "Extraction done: %d records, new watermark=%s, %.1fs",
    len(records), new_wm, time.perf_counter() - t0,
  )

  return records, new_wm
