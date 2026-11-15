from pathlib import Path
import logging
import pandas as pd
from io import BytesIO
from google.cloud import bigquery, storage
from src.logging_config import configure_logging
from src.util import get_str_date


configure_logging()
logger = logging.getLogger(__name__)

def get_gcs_blob(bucket_name, destination):
  """
  Create a reference to an object in a Cloud Storage bucket.

  Parameters
  ----------
  bucket_name : str
    Name of the bucket, without the `gs://` prefix.
  destination : str
    Object name within the bucket, including any folder prefixes.

  Returns
  -------
  blob : google.cloud.storage.blob.Blob
    Reference to the destination object.
  """
  client = storage.Client()
  blob = client.bucket(bucket_name).blob(destination)

  return blob

def save_df_locally(df, local_dir, destination, file_format="csv"):
  """
  Save a DataFrame locally as CSV or Parquet without its index.

  Parameters
  ----------
  df : pandas.DataFrame
    DataFrame to save.
  local_dir : str or pathlib.Path
    Base directory for local output.
  destination : str
    Relative output path, including the filename and extension.
  file_format : str, optional`
    Output format, choose from {'csv', 'parquet'}. Default is 'csv'.

  Returns
  -------
  str
    Path to the saved file.

  Raises
  ------
  ValueError
    If `file_format` is neither 'csv' nor 'parquet'.
  """
  if file_format not in {"csv", "parquet"}:
    raise ValueError("file_format must be 'csv' or 'parquet'.")
  path = Path(local_dir) / destination
  path.parent.mkdir(parents=True, exist_ok=True)

  if file_format == "csv":
    df.to_csv(path, index=False)
  else:
    df.to_parquet(path, engine="pyarrow", index=False)

  return str(path)


def save_csv(df, destination, bucket_name=None, local_dir="data"):
  """
  Save a DataFrame as CSV locally or directly to Cloud Storage.

  Parameters
  ----------
  df : pandas.DataFrame
    DataFrame to save.
  destination : str
    Relative file path or Cloud Storage object name, including the
    filename and `.csv` extension.
  bucket_name : str or None, optional
    Destination bucket name, without the `gs://` prefix. If None,
    save locally. Default is None.
  local_dir : str or pathlib.Path, optional
    Base directory for local output. Ignored when `bucket_name` is
    provided. Default is 'data'.

  Returns
  -------
  str
    Local file path or `gs://` URI of the saved CSV.

  Raises
  ------
  ValueError
    If `bucket_name` is empty or contains only whitespace.
  """
  if bucket_name is not None:
    if not bucket_name.strip():
      raise ValueError("bucket_name must not be empty.")
    
    blob = get_gcs_blob(bucket_name, destination)

    blob.upload_from_string(df.to_csv(index=False), 
      content_type="text/csv; charset=utf-8")

    return f"gs://{bucket_name}/{destination}"

  path = save_df_locally(df, local_dir, destination)

  return str(path)

def save_parquet(df, destination, bucket_name=None, local_dir="data"):
  """
  Save a DataFrame as Parquet locally or directly to Cloud Storage.

  Parameters
  ----------
  df : pandas.DataFrame
    DataFrame to save.
  destination : str
    Relative file path or Cloud Storage object name, including the
    filename and `.parquet` extension.
  bucket_name : str or None, optional
    Destination bucket name, without the `gs://` prefix. If None,
    save locally. Default is None.
  local_dir : str or pathlib.Path, optional
    Base directory for local output. Ignored when `bucket_name` is
    provided. Default is 'data'.

  Returns
  -------
  str
    Local file path or `gs://` URI of the saved Parquet file.

  Raises
  ------
  ValueError
    If `bucket_name` is empty or contains only whitespace.
  """
  if bucket_name is not None:
    if not bucket_name.strip():
      raise ValueError("bucket_name must not be empty.")
    
    blob = get_gcs_blob(bucket_name, destination)

    with BytesIO() as buffer:
      df.to_parquet(buffer, engine="pyarrow", index=False)

      blob.upload_from_file(
        buffer,
        rewind=True,
        content_type="application/octet-stream")
      
    return f"gs://{bucket_name}/{destination}"

  path = save_df_locally(df, local_dir, destination, file_format="parquet")

  return str(path)
    

  