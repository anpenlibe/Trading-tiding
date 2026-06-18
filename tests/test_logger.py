"""Regression tests for the logging setup.

Pins the handler wiring, that re-setup doesn't duplicate handlers, the
level-colorized console formatter, and that the dead TradingLogger wrapper +
get_*_logger factories (the only consumer used them via `.logger.logger.x`,
never their structured methods) stay removed.
"""

import logging

import src.utils.logger as logmod
from src.utils.logger import setup_logger, ColoredFormatter


def test_handlers_wired_and_not_duplicated():
    log = setup_logger("test_logger_pin", "test_logger_pin.log")
    assert isinstance(log, logging.Logger)
    assert len(log.handlers) == 3  # file + console + shared error.log
    # Re-setup with the same name must not stack duplicate handlers.
    again = setup_logger("test_logger_pin", "test_logger_pin.log")
    assert len(again.handlers) == 3


def test_only_error_handler_when_file_and_console_disabled():
    log = setup_logger("test_logger_err_only", log_file=None, console_output=False)
    assert len(log.handlers) == 1  # just the shared error handler


def test_colored_formatter_colorizes_by_level():
    record = logging.LogRecord("n", logging.INFO, __file__, 1, "hello", None, None)
    out = ColoredFormatter().format(record)
    assert "hello" in out
    assert "\x1b[32m" in out  # INFO is green


def test_removed_logger_helpers_stay_removed():
    for name in ("TradingLogger", "get_data_logger", "get_trading_logger",
                 "get_ai_logger", "get_monitor_logger"):
        assert not hasattr(logmod, name), f"{name} was dead and should stay removed"
