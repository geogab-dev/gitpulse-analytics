import logging
import sys
from logging import Logger, LoggerAdapter

import colorlog
from prefect.exceptions import MissingContextError
from prefect.logging import get_run_logger

from core.config.settings import settings

# ANSI helpers for coloring log messages (works both inside and outside Prefect)
_RESET = "\033[0m"
_ANSI: dict[str, str] = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "magenta": "\033[95m",
    "cyan": "\033[96m",
}


def _color(name: str, text: str | int) -> str:
    return f"{_ANSI[name]}{text}{_RESET}"


def red(text: str | int) -> str:
    return _color("red", text)


def green(text: str | int) -> str:
    return _color("green", text)


def yellow(text: str | int) -> str:
    return _color("yellow", text)


def blue(text: str | int) -> str:
    return _color("blue", text)


def magenta(text: str | int) -> str:
    return _color("magenta", text)


def cyan(text: str | int) -> str:
    return _color("cyan", text)


def _configure_logger(logger: Logger) -> None:
    """Configure a logger with colorized output and proper formatting."""
    if logger.handlers:
        return

    logger.setLevel(settings.logging.level.upper())

    handler = colorlog.StreamHandler(sys.stdout)

    if settings.logging.use_colors:
        formatter = colorlog.ColoredFormatter(
            fmt="%(asctime)s.%(msecs)03d | %(log_color)s%(levelname)-7s%(reset)s | %(message)s",
            datefmt="%H:%M:%S",
            log_colors={
                "DEBUG": "white",
                "INFO": "cyan",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s.%(msecs)03d | %(levelname)-7s | %(message)s",
            datefmt="%H:%M:%S",
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False


def get_logger(name: str | None = None) -> Logger | LoggerAdapter[Logger]:
    """
    Get a logger that works both inside and outside of Prefect flows.

    When called within a Prefect flow context, returns the Prefect run logger.
    Otherwise, returns a standard logger with colorized output.

    Args:
        name: Logger name (defaults to "core"). Use __name__ when calling from modules.

    Returns:
        A configured Logger instance.
    """
    try:
        return get_run_logger()
    except MissingContextError:
        # not in a Prefect context, use standard logger
        pass

    logger_name: str = name or "core"
    logger: Logger = logging.getLogger(logger_name)

    _configure_logger(logger)

    return logger
