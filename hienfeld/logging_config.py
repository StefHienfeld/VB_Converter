# hienfeld/logging_config.py
"""
Logging configuration for Hienfeld VB Converter.

Developer Mode:
    Set environment variable: HIENFELD_DEV_MODE=1
    This enables:
    - DEBUG level logging
    - Colored console output
    - Performance timing logs
    - Detailed service initialization logs
"""
import logging
import sys
import os
from typing import Optional


# ANSI color codes for terminal output
class LogColors:
    """ANSI color codes for colored logging."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Levels
    DEBUG = "\033[36m"      # Cyan
    INFO = "\033[32m"       # Green
    WARNING = "\033[33m"    # Yellow
    ERROR = "\033[31m"      # Red
    CRITICAL = "\033[35m"   # Magenta

    # Special markers
    PHASE = "\033[1;34m"    # Bold Blue
    SUCCESS = "\033[1;32m"  # Bold Green
    FAIL = "\033[1;31m"     # Bold Red
    TIMING = "\033[35m"     # Magenta


class ColoredFormatter(logging.Formatter):
    """
    Formatter that adds colors to console output.

    Only adds colors when outputting to a TTY (not when piped to file).
    """

    LEVEL_COLORS = {
        logging.DEBUG: LogColors.DEBUG,
        logging.INFO: LogColors.INFO,
        logging.WARNING: LogColors.WARNING,
        logging.ERROR: LogColors.ERROR,
        logging.CRITICAL: LogColors.CRITICAL,
    }

    def __init__(self, *args, use_colors: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_colors = use_colors and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        if not self.use_colors:
            return super().format(record)

        # Color the level name
        levelname = record.levelname
        if record.levelno in self.LEVEL_COLORS:
            color = self.LEVEL_COLORS[record.levelno]
            record.levelname = f"{color}{levelname}{LogColors.RESET}"

        # Color special markers in message
        message = record.getMessage()
        if "⏱️" in message or "CHECKPOINT" in message or "FINISH" in message:
            # Timing messages
            message = f"{LogColors.TIMING}{message}{LogColors.RESET}"
        elif "✅" in message or "SUCCESS" in message:
            # Success messages
            message = f"{LogColors.SUCCESS}{message}{LogColors.RESET}"
        elif "❌" in message or "FAILED" in message:
            # Failure messages
            message = f"{LogColors.FAIL}{message}{LogColors.RESET}"
        elif "🚀" in message or "BEGIN" in message or "PHASE" in message:
            # Phase markers
            message = f"{LogColors.PHASE}{message}{LogColors.RESET}"

        # Temporarily override message for formatting
        record.msg = message
        record.args = ()

        formatted = super().format(record)
        return formatted


def is_dev_mode() -> bool:
    """
    Check if developer mode is enabled.

    Returns:
        True if HIENFELD_DEV_MODE environment variable is set to 1, yes, or true
    """
    dev_mode = os.getenv('HIENFELD_DEV_MODE', '').lower()
    return dev_mode in ('1', 'yes', 'true', 'on')


def setup_logging(
    level: Optional[int] = None,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None,
    use_colors: bool = True
) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        level: Logging level (default: INFO, or DEBUG if dev mode enabled)
        log_file: Optional file path for log output
        format_string: Custom format string for log messages
        use_colors: Whether to use colored output (default: True)

    Returns:
        Configured logger instance
    """
    # Auto-detect dev mode
    dev_mode = is_dev_mode()

    # Default level based on mode
    if level is None:
        level = logging.DEBUG if dev_mode else logging.INFO

    # Enhanced format string for dev mode
    if format_string is None:
        if dev_mode:
            format_string = '[%(asctime)s] %(levelname)-8s | %(name)-25s | %(message)s'
        else:
            format_string = '[%(asctime)s] %(levelname)s - %(name)s - %(message)s'

    # Get root logger for hienfeld package
    logger = logging.getLogger('hienfeld')
    logger.setLevel(level)

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if use_colors:
        formatter = ColoredFormatter(format_string, datefmt='%H:%M:%S')
    else:
        formatter = logging.Formatter(format_string, datefmt='%Y-%m-%d %H:%M:%S')

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional) - never colored
    if log_file:
        file_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Log dev mode status
    if dev_mode:
        logger.info("🔧 DEVELOPER MODE ENABLED - Verbose logging active")

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(f'hienfeld.{name}')


def log_section(logger: logging.Logger, title: str, width: int = 80) -> None:
    """
    Log a section header for better readability.

    Args:
        logger: Logger instance
        title: Section title
        width: Width of the separator line
    """
    separator = "=" * width
    logger.info(separator)
    logger.info(f"  {title}")
    logger.info(separator)

