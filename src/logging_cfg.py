from loguru import logger
import sys
import json

def setup_logging(level: str = "INFO"):
    logger.remove()
    
    logger.add(
        sys.stdout,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {module}:{function}:{line} - {message}",
        level=level,
        serialize=False,
        backtrace=True,
        diagnose=True
    )
    
    logger.add(
        sys.stderr,
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {module}:{function}:{line} - {message}",
        backtrace=True,
        diagnose=True,
        filter=lambda record: record["level"].no >= 40
    )
    
    return logger

def get_logger(name: str = None):
    if name:
        return logger.bind(module_name=name)
    return logger

logger = setup_logging()