import logging
import pandas as pd
from src.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

"""
| Priority | Task | Status |
|---|---|---|
| 1 | Schema validation | Start here |
| 2 | String cleaning | Done |
| 3 | Data type conversion | Done |
| 4 | Missing-value handling | Done |
| 5 | Coordinate validation | Next |
| 6 | Duplicate handling | After profiling |
| 7 | Unit tests | Alongside each function |
"""

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

  df[NUMERIC_COLS] = df[NUMERIC_COLS].appy(pd.to_numeric, errors="coerce")
  df[DATETIME_COLS] = df[DATETIME_COLS].appy(
    pd.to_datetime, errors="coerce", utc=True)

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
  df = clean_strings(raw_df)
  df = convert_data_types(df)
  df = validate_coordinates(df)
  df = remove_duplicates(df, subset=["unique_key"], keep="last")

  return df

