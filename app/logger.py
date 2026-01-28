"""
Centralized logging configuration with sensitive data masking
"""

import logging
import sys
import re
from pathlib import Path
from datetime import datetime


class SensitiveDataFilter(logging.Filter):
    """Filter to mask sensitive data in log messages"""

    def __init__(self):
        super().__init__()
        self.password_patterns = [
            r"-P\s+[^\s]+",  # -P password
            r"--password\s+[^\s]+",  # --password
            r"password\s*=\s*[^\s]+",  # password=value
        ]

    def filter(self, record):
        """Mask sensitive data in log record"""
        if record.msg and isinstance(record.msg, str):
            record.msg = self._mask_sensitive_data(record.msg)

        if record.args and isinstance(record.args, tuple):
            # Process each argument if it's a string
            args = list(record.args)
            for i, arg in enumerate(args):
                if isinstance(arg, str):
                    args[i] = self._mask_sensitive_data(arg)
            record.args = tuple(args)

        return True

    def _mask_sensitive_data(self, text: str) -> str:
        """Mask passwords and other sensitive data"""
        if not text:
            return text

        # Mask common password patterns
        for pattern in self.password_patterns:
            text = re.sub(pattern, lambda m: m.group(0).split()[0] + " ***", text)

        # Mask any standalone password-like strings (crude but helpful)
        # This catches passwords that might be logged in unexpected places
        text = re.sub(r"([Pp]assword\s*[:=]?\s*)([^\s]+)", r"\1***", text)

        return text


def setup_logger(name="POSAdminTool"):
    """Setup and configure logger with sensitive data filtering"""
    # Create logs directory
    log_dir = Path.home() / ".pos_admin_tool" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Remove existing handlers
    logger.handlers.clear()

    # File handler
    log_file = log_dir / f"pos_admin_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add sensitive data filter
    sensitive_filter = SensitiveDataFilter()
    file_handler.addFilter(sensitive_filter)
    console_handler.addFilter(sensitive_filter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger(name="POSAdminTool"):
    """Get the logger instance"""
    return logging.getLogger(name)
