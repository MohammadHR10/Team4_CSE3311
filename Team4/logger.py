# ================================================================================
# LOGGING CONFIGURATION MODULE
# ================================================================================
# This module sets up centralized logging for the club house management system.
# It provides both console and file logging with rotation to manage log file sizes.
#
# Features:
# - Configurable log levels via environment variables
# - Rotating file handler to prevent large log files
# - Dual output: console for development, files for production
# - Structured log format with timestamps and source locations
# ================================================================================

import logging
from logging.handlers import RotatingFileHandler
import os

# Configuration from environment variables with sensible defaults
LOG_LEVEL = os.getenv("APP_LOG_LEVEL", "INFO").upper()          # Log level (DEBUG, INFO, WARNING, ERROR)
LOG_FILE = os.getenv("APP_LOG_FILE", "club_house.log")          # Log file name
MAX_BYTES = int(os.getenv("APP_LOG_MAX_BYTES", 5 * 1024 * 1024)) # Max file size: 5MB
BACKUP_COUNT = int(os.getenv("APP_LOG_BACKUP_COUNT", 3))         # Number of backup files to keep

def get_logger(name: str = None) -> logging.Logger:
    """
    Get a configured logger instance for the specified module.
    
    Creates a logger with both console and file handlers if not already configured.
    The logger includes:
    - Console output for immediate feedback during development
    - Rotating file output for persistent logging in production
    - Structured formatting with timestamps and source information
    
    Args:
        name (str): Name of the logger, typically __name__ from calling module
        
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Return existing logger if already configured
    if logger.handlers:
        return logger

    # Set the log level from environment variable
    level = getattr(logging, LOG_LEVEL, logging.INFO)
    logger.setLevel(level)

    # Console Handler - for development and immediate feedback
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"))
    logger.addHandler(ch)

    # File Handler - for persistent logging with rotation
    fh = RotatingFileHandler(LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s"))
    logger.addHandler(fh)

    # Prevent log messages from being passed to parent loggers
    logger.propagate = False
    return logger