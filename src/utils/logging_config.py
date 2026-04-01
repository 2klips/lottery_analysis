import logging
import sys


def setup_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    """Configure and return a module logger.

    Args:
        name: Logger name, typically ``__name__``.
        level: Logging level constant from ``logging`` module.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Return project logger with default configuration.

    Args:
        name: Logger name, typically ``__name__``.

    Returns:
        Configured logger instance.
    """
    return setup_logging(name)
