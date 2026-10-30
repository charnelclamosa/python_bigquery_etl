import logging
from fastapi import FastAPI, APIRouter, status, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from src.logging_config import configure_logging
from src.extract import extract_service_requests

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

  service_requests = extract_service_requests()

  return service_requests

app = FastAPI()
app.include_router(router)