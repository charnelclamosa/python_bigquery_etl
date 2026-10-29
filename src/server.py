import logging
from fastapi import FastAPI, APIRouter, status, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from src.logging_config import configure_logging

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


app = FastAPI()
app.include_router(router)