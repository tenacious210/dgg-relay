from logging.handlers import RotatingFileHandler
from logging import StreamHandler
from google.cloud.logging.handlers import CloudLoggingHandler
from google.cloud.logging_v2.handlers import setup_logging
import google.cloud.logging
import logging
import sys

log_format = "[%(asctime)s] %(name)s:%(levelname)s: %(message)s"
log_formatter = logging.Formatter(log_format)
logger = logging.getLogger("dgg_relay")
log_stream_handler = StreamHandler(sys.stdout)
log_stream_handler.setLevel(logging.DEBUG)
log_stream_handler.setFormatter(log_formatter)
logger.addHandler(log_stream_handler)
log_cloud_handler = None


def enable_cloud_logging():
    logger_client = google.cloud.logging.Client()
    log_cloud_handler = CloudLoggingHandler(logger_client)
    log_cloud_handler.setLevel(logging.DEBUG)
    logger.addHandler(log_cloud_handler)
    logger.info("Cloud logging enabled")
