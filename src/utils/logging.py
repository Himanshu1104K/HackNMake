import logging
import sys
import os
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels"""

    # Color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record):
        # Get the original formatted message
        log_message = super().format(record)

        # Add color based on log level
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        # Apply color to the entire log message
        colored_message = f"{color}{log_message}{reset}"

        return colored_message


def supports_color() -> bool:
    """
    Check if the terminal supports color output.

    Returns:
        True if colors are supported, False otherwise
    """
    # Force colors if FORCE_COLOR is set
    if os.getenv("FORCE_COLOR"):
        return True

    # For development environments, be more permissive
    if os.getenv("DEVELOPMENT") or os.getenv("DEV"):
        return True

    # Check if we're in a terminal
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        # Even if not a TTY, allow colors if FORCE_COLOR is set
        return os.getenv("FORCE_COLOR") is not None

    # Check environment variables that disable colors
    if os.getenv("NO_COLOR") and not os.getenv("FORCE_COLOR"):
        return False

    # Check if we're in a CI environment (but allow colors in some CI)
    if os.getenv("CI") and not os.getenv("FORCE_COLOR"):
        return False

    # Check TERM environment variable for color support
    term = os.getenv("TERM", "").lower()
    if term in ["dumb", "unknown"] and not os.getenv("FORCE_COLOR"):
        return False

    # For Linux terminals, be more permissive
    if sys.platform.startswith("linux"):
        # Most Linux terminals support colors, even with TERM=dumb
        return True

    # Check if we're in a virtual machine or container
    if os.path.exists("/.dockerenv") or os.getenv("VIRTUAL_ENV"):
        # Still allow colors in containers/VMs if terminal supports it
        return True

    # Default to True for most terminals
    return True


def setup_logging(level: str = "INFO", use_colors: bool = None) -> None:
    """
    Setup centralized logging configuration for the entire application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_colors: Whether to use colored output (auto-detected if None)
    """
    # Convert string level to logging constant
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Auto-detect color support if not specified
    if use_colors is None:
        use_colors = supports_color()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)

    # Create formatter (colored or plain)
    if use_colors:
        formatter = ColoredFormatter(
            fmt="%(asctime)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s",
            datefmt="%d-%m-%Y %H:%M:%S",
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s",
            datefmt="%d-%m-%Y %H:%M:%S",
        )

    # Set formatter for console handler
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)

    # Clear any existing handlers to avoid duplicates
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    # Filter out external library logs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("qdrant_client").setLevel(logging.WARNING)
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("firebase_admin").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance with the configured format.

    Args:
        name: Logger name (optional, defaults to module name)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Initialize logging when module is imported
setup_logging()
