import logging
import pandas as pd
from fastapi import FastAPI, APIRouter, status, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from src.logging_config import configure_logging
from src.extract import extract_service_requests
from src.transform import transform
from src.utils import save_watermark

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

  if not service_requests:
    logger.info("Nothing to load, watermark unchanged")
    return {"extracted": 0, "loaded": 0, "watermark": None}

  save_watermark(new_wm) 
  logger.info("Watermark saved: %s", new_wm)

  o = {
    "extracted": len(service_requests), 
    "loaded": len(service_requests), 
    "watermark": new_wm
  }

  return o

@router.get("/etl/run")
def run_pipeline():
  """_summary_
   Usage:
      curl http://localhost:8080/api/etl/run
  """
  raw_df = pd.read_csv("data/service_requests.csv")
  df = raw_df.copy()

  logger.info("Running transformation")
  df = transform(df)
  df.to_csv("data/cleaned.csv", index=False)
  

app = FastAPI()
app.include_router(router)