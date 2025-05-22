"""
Logging module.

This module sets up structured logging for the application.
"""
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from api.core.config import settings


class JsonFormatter(logging.Formatter):
    """
    JSON formatter for logging.
    
    Formats log records as JSON objects.
    """
    
    def __init__(self):
        """Initialize formatter."""
        super().__init__()
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.
        
        Args:
            record: Log record
            
        Returns:
            str: Formatted log record as JSON string
        """
        log_object = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "path": record.pathname,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if available
        if record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            log_object["exception"] = {
                "type": exc_type.__name__,
                "message": str(exc_value),
            }
        
        # Add extra attributes from record
        if hasattr(record, "props"):
            log_object.update(record.props)
        
        return json.dumps(log_object)


class StructuredLogger(logging.Logger):
    """
    Structured logger.
    
    Extends the standard logger with structured logging capabilities.
    """
    
    def _log_with_props(
        self,
        level: int,
        msg: str,
        props: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs
    ):
        """
        Log with additional properties.
        
        Args:
            level: Log level
            msg: Log message
            props: Additional properties for structured logging
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        if props:
            kwargs["extra"] = {"props": props}
        self.log(level, msg, *args, **kwargs)
    
    def debug_with_props(self, msg: str, props: Optional[Dict[str, Any]] = None, *args, **kwargs):
        """Log debug message with properties."""
        self._log_with_props(logging.DEBUG, msg, props, *args, **kwargs)
    
    def info_with_props(self, msg: str, props: Optional[Dict[str, Any]] = None, *args, **kwargs):
        """Log info message with properties."""
        self._log_with_props(logging.INFO, msg, props, *args, **kwargs)
    
    def warning_with_props(self, msg: str, props: Optional[Dict[str, Any]] = None, *args, **kwargs):
        """Log warning message with properties."""
        self._log_with_props(logging.WARNING, msg, props, *args, **kwargs)
    
    def error_with_props(self, msg: str, props: Optional[Dict[str, Any]] = None, *args, **kwargs):
        """Log error message with properties."""
        self._log_with_props(logging.ERROR, msg, props, *args, **kwargs)
    
    def critical_with_props(self, msg: str, props: Optional[Dict[str, Any]] = None, *args, **kwargs):
        """Log critical message with properties."""
        self._log_with_props(logging.CRITICAL, msg, props, *args, **kwargs)


# Register custom logger class
logging.setLoggerClass(StructuredLogger)


def get_logger(name: str) -> StructuredLogger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        StructuredLogger: Logger instance
    """
    return logging.getLogger(name)


def setup_logging() -> None:
    """
    Set up logging.
    
    Configures logging handlers and formatters based on environment.
    """
    # Determine log level from settings
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Set formatter based on environment
    if settings.ENVIRONMENT in ("production", "staging"):
        console_handler.setFormatter(JsonFormatter())
    else:
        # Use a more readable format for development
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
    
    # Add handler to root logger
    root_logger.addHandler(console_handler)
    
    # Set up specific loggers
    for logger_name, logger_level in (
        ("uvicorn", log_level),
        ("uvicorn.error", log_level),
        ("uvicorn.access", log_level),
        ("fastapi", log_level),
        ("sqlalchemy.engine", logging.WARNING),
        ("aio_pika", logging.WARNING),
        ("asyncio", logging.WARNING),
    ):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logger_level)
        # Ensure propagation to the root logger
        logger.propagate = True
