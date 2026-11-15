import os
import logging
import pandas as pd
from fastapi import FastAPI, APIRouter, status, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from uuid import uuid4
from src.logging_config import configure_logging
from src.extract import extract_service_requests
from src.transform import transform
from src.load import save_csv, save_parquet
from src.util import save_watermark, get_str_date

configure_logging()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

@router.get("/healthz")
def healthz():
  """
  API health check.

  Usage:
    curl http://localhost:8080/api/healthz
  """
  return {"status": "ok"}

@router.get("/etl/extract")
def read_service_requests():
  """_summary_

  Usage:
    curl http://localhost:8080/api/etl/extract
  """
  logger.info("Getting service requests")

  service_requests, new_wm = extract_service_requests()

  if service_requests.empty:
    logger.info("Nothing to load, watermark unchanged")
    return {"extracted": 0, "loaded": 0, "watermark": None}

  save_watermark(new_wm) 
  logger.info("Watermark saved: %s", new_wm)

  o = {
    "extracted": len(service_requests), 
    "loaded": len(service_requests), 
    "watermark": new_wm
  }

  return o, service_requests

@router.post("/etl/run")
def run_pipeline():
  """_summary_
  Usage:
    curl -X POST http://localhost:8080/api/etl/run
  """
  environment = os.getenv("APP_ENV", "local")
  if environment not in {"local", "uat"}:
    raise ValueError("APP_ENV must be 'local' or 'uat'.")

  bucket_name = None

  if environment == "uat":
    bucket_name = os.getenv("GCS_BUCKET")
    if not bucket_name or not bucket_name.strip():
      raise ValueError("GCS_BUCKET is required in the cloud environment.")

  run_date = get_str_date()
  run_id = uuid4().hex

  logger.info("Extracting service requests")

  raw_df, new_wm = extract_service_requests()

  if raw_df.empty:
    logger.info("Nothing to load, watermark unchanged")
    return {
      "extracted": 0,
      "transformed": 0,
      "watermark": None,
      "run date": run_date,
      "run ID": run_id,
      "outputs": {},
    }

  logger.info("Running transformation")
  cleaned_df = transform(raw_df.copy())

  logger.info("Saving raw CSV and cleaned Parquet")
  raw_path = save_csv(
    raw_df,
    destination=f"{run_date}/raw_{run_id}.csv",
    bucket_name=bucket_name)

  cleaned_path = save_parquet(
    cleaned_df,
    destination=f"{run_date}/cleaned_{run_id}.parquet",
    bucket_name=bucket_name)

  """
  TODO: Add the BigQuery load here when it is ready.
  Keep watermark saving after all required output/load steps.
  """
  save_watermark(new_wm)
  logger.info("Watermark saved: %s", new_wm)

  return {
    "extracted": len(raw_df),
    "transformed": len(cleaned_df),
    "watermark": new_wm,
    "run date": run_date,
    "run ID": run_id,
    "outputs": {"raw": raw_path, "cleaned": cleaned_path}
  }


app = FastAPI()
app.include_router(router)