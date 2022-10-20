from logging.handlers import RotatingFileHandler
from logging import StreamHandler
import logging
import sys

log_format = "[%(asctime)s] %(name)s:%(levelname)s: %(message)s"
log_file_handler = RotatingFileHandler("logs.log", maxBytes=250000000, backupCount=1)
logging.basicConfig(level=logging.INFO, format=log_format, handlers=[log_file_handler])
logger = logging.getLogger("dgg_relay")
log_stream_handler = StreamHandler(sys.stdout)
log_stream_handler.setLevel(logging.DEBUG)
log_formatter = logging.Formatter(log_format)
log_stream_handler.setFormatter(log_formatter)
logger.addHandler(log_stream_handler)
