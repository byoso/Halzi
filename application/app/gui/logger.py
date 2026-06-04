from app.config import LOG_LEVEL
from app.silly_engine.logger import Logger

logger = Logger("GUI", display_level=False)
logger.set_level(LOG_LEVEL)