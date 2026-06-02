
from app.silly_engine.logger import Logger
from app.config import LOG_LEVEL

logger = Logger("app.database", display_level=False)
logger.set_level(LOG_LEVEL)