import logging
import pandas as pd
import time
from src.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


NUMERIC_COLS = [
  "latitude",
  "longitude",
]
DATETIME_COLS = [
  "created_date",
  "resolution_action_updated_date",
]

def clean_strings(df : pd.DataFrame) -> pd.DataFrame:
  """
  Clean string columns by removing leading and trailing whitespace
  and replacing empty strings with pandas missing values.

  Parameters
  ----------
  df : pandas.DataFrame
    DataFrame containing the source records.

  Returns
  -------
  pandas.DataFrame
    A cleaned copy of the input DataFrame.
  """
  df = df.copy()

  string_cols = df.select_dtypes(include=["object", "string"]).columns

  df[string_cols] = df[string_cols].apply(lambda col: col.str.strip())
  df[string_cols] = df[string_cols].replace("", pd.NA)

  return df

def convert_data_types(df : pd.DataFrame) -> pd.DataFrame:
  """
  Convert specified columns to their expected data types.

  Numeric columns are converted using pandas.to_numeric(),
  while timestamp columns are converted using pandas.to_datetime().
  Invalid values are coerced into missing values.

  Parameters
  ----------
  df : pandas.DataFrame
    DataFrame containing the source records.

  Returns
  -------
  pandas.DataFrame
    A cleaned copy of the input DataFrame.
  """
  df = df.copy()

  df[NUMERIC_COLS] = df[NUMERIC_COLS].apply(pd.to_numeric, errors="coerce")
  df[DATETIME_COLS] = df[DATETIME_COLS].apply(
    pd.to_datetime, errors="coerce")

  return df

def validate_coordinates(df : pd.DataFrame) -> pd.DataFrame:
  """
  Validate latitude and longitude values against their respective
  geographic coordinate ranges.

  Invalid coordinates are replaced with pandas missing values.
  Records are preserved even when their coordinates are invalid.

  Parameters
  ----------
  df : pandas.DataFrame
    DataFrame containing the source records.

  Returns
  -------
  pandas.DataFrame
    A cleaned copy of the input DataFrame.
  """
  df = df.copy()

  valid_lat = df["latitude"].between(-90, 90)
  valid_lon = df["longitude"].between(-180, 180)

  invalid_coordinates = (
    (df["latitude"].notna() & ~valid_lat)
    | (df["longitude"].notna() & ~valid_lon)
  )

  df.loc[invalid_coordinates, ["latitude", "longitude"]] = pd.NA

  return df

def remove_duplicates(df, subset=None, keep="last") -> pd.DataFrame:
  """
  Remove duplicate records based on all columns except `unique_key` column.

  Parameters
  ----------
  df : pandas.DataFrame
    DataFrame containing the records to deduplicate.
  subset : list of str, optional
    Columns used to identify duplicate records.
    If None, all columns are considered.
  keep : {'first', 'last', False}, default 'last'
    Determines which duplicate records to retain.
    'first' retains the first occurrence.
    'last' retains the last occurrence.
    False removes all occurrences of duplicated records.

  Returns
  -------
  pandas.DataFrame
    A deduplicated copy of the input DataFrame.
  """
  df = df.copy()

  return df.drop_duplicates(subset=subset, keep=keep,).reset_index(drop=True)

def strip_internal_spaces(df):
  """
  Remove internal multiple spaces between words.

  Parameters
  ----------
  df : pandas.DataFrame
    DataFrame containing records with multiple internal multiple spaces.

  Returns
  -------
  pandas.DataFrame
    A copy of the input DataFrame where the internal multiple spaces are removed.
  """
  df = df.copy()

  for col in ['incident_address', 'street_name']:
    df[col] = (
      df[col]
      .str.replace(r'\s+', ' ', regex=True)
      .str.strip()
  )

  return df

def str_to_title(df):
  """
  Parse the all caps texts to 'title' format.

  Parameters
  ----------
  df : pandas.DataFrame
    DataFrame containing records where there are records in all caps.

  Returns
  -------
  pandas.DataFrame
    A copy of the input DataFrame where the all caps strings are parsed to 'title' format.
  """
  df = df.copy()

  cols = ['complaint_type', 'incident_address', 'street_name', 
    'address_type', 'landmark', 'city', 'borough', 'park_borough']

  for col in cols:
    df[col] = df[col].str.title()

  return df

def transform(raw_df : pd.DataFrame) -> pd.DataFrame:
  """
  Clean and transform the extracted NYC 311 dataset.

  Applies string cleaning, data type conversion, and coordinate
  validation in sequence.

  Parameters
  ----------
  raw_df : pandas.DataFrame
    Raw DataFrame extracted from the NYC 311 API.

  Returns
  -------
  df : pandas.DataFrame
    Transformed DataFrame ready for downstream data validation
    and dimensional modeling.
  """
  logger.info("Running transformation process")
  t0 = time.perf_counter()

  df = clean_strings(raw_df)
  df = convert_data_types(df)
  df = validate_coordinates(df)
  df = str_to_title(df)
  df = strip_internal_spaces(df)
  df = remove_duplicates(df, subset=["unique_key"], keep="last")

  logger.info("Transformation process done, runtime: %.1fs", 
    time.perf_counter() - t0)

  return df

