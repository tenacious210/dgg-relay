from logging.handlers import RotatingFileHandler
import logging
import sys

log_format = "[%(asctime)s] %(name)s:%(levelname)s: %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[RotatingFileHandler("logs.log", maxBytes=250000000, backupCount=1)],
)
logger = logging.getLogger("dgg_relay")
log_stream_handler = logging.StreamHandler(sys.stdout)
log_stream_handler.setLevel(logging.DEBUG)
log_formatter = logging.Formatter(log_format)
log_stream_handler.setFormatter(log_formatter)
logger.addHandler(log_stream_handler)
