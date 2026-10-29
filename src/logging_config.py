import os
import sys
import logging

# ============================================================================
# LOGGING
# ============================================================================
def configure_logging() -> None:
  log_level = os.getenv("LOG_LEVEL", "INFO").upper()

  logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout)