"""
Module: logger.py
Purpose: Centralized logging configuration for trading bot
Author: Trading Bot Developer
Created: 2025-06-12
Modified: 2025-06-12
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""
    
    grey = "\x1b[38;21m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    red = "\x1b[31m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    
    FORMATS = {
        logging.DEBUG: grey + "%(asctime)s - %(name)s - %(levelname)s - %(message)s" + reset,
        logging.INFO: green + "%(asctime)s - %(name)s - %(levelname)s - %(message)s" + reset,
        logging.WARNING: yellow + "%(asctime)s - %(name)s - %(levelname)s - %(message)s" + reset,
        logging.ERROR: red + "%(asctime)s - %(name)s - %(levelname)s - %(message)s" + reset,
        logging.CRITICAL: bold_red + "%(asctime)s - %(name)s - %(levelname)s - %(message)s" + reset
    }
    
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    console_output: bool = True,
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Set up a logger with file and console handlers.
    
    Args:
        name: Logger name (usually __name__)
        log_file: Log file name (without path)
        level: Logging level
        console_output: Whether to output to console
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # File handler with rotation
    if log_file:
        file_path = os.path.join(LOGS_DIR, log_file)
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Console handler with colors
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ColoredFormatter())
        logger.addHandler(console_handler)
    
    # Error file handler (captures all errors from all modules)
    error_file_path = os.path.join(LOGS_DIR, 'error.log')
    error_handler = RotatingFileHandler(
        error_file_path,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    error_handler.setFormatter(error_formatter)
    logger.addHandler(error_handler)
    
    return logger


class TradingLogger:
    """Specialized logger for trading operations with structured logging"""
    
    def __init__(self, name: str, log_file: str):
        self.logger = setup_logger(name, log_file)
        
    def log_api_call(self, api_name: str, symbol: str, success: bool, 
                     response_time: float, error: Optional[str] = None):
        """Log API call with structured data"""
        if success:
            self.logger.info(
                f"API_CALL | {api_name} | {symbol} | SUCCESS | {response_time:.3f}s"
            )
        else:
            self.logger.error(
                f"API_CALL | {api_name} | {symbol} | FAILED | {response_time:.3f}s | {error}"
            )
            
    def log_data_quality(self, symbol: str, issue: str, severity: str = "WARNING"):
        """Log data quality issues"""
        log_method = getattr(self.logger, severity.lower(), self.logger.warning)
        log_method(f"DATA_QUALITY | {symbol} | {issue}")
        
    def log_indicator_calculation(self, symbol: str, indicator: str, value: float):
        """Log indicator calculations"""
        self.logger.debug(f"INDICATOR | {symbol} | {indicator} | {value:.4f}")
        
    def log_cache_operation(self, operation: str, symbol: str, hit: bool = True):
        """Log cache operations"""
        status = "HIT" if hit else "MISS"
        self.logger.debug(f"CACHE | {operation} | {symbol} | {status}")
        
    def log_database_operation(self, operation: str, table: str, records: int, 
                               duration: float):
        """Log database operations"""
        self.logger.info(
            f"DATABASE | {operation} | {table} | {records} records | {duration:.3f}s"
        )
        
    def log_daily_summary(self, stats: dict):
        """Log daily summary statistics"""
        self.logger.info("="*60)
        self.logger.info("DAILY SUMMARY")
        self.logger.info("="*60)
        for key, value in stats.items():
            self.logger.info(f"{key}: {value}")
        self.logger.info("="*60)


# Pre-configured loggers for different modules
def get_data_logger() -> TradingLogger:
    """Get logger for data collection module"""
    return TradingLogger('data_collector', 'data_collector.log')


def get_trading_logger() -> TradingLogger:
    """Get logger for trading operations"""
    return TradingLogger('paper_trader', 'paper_trader.log')


def get_ai_logger() -> TradingLogger:
    """Get logger for AI brain module"""
    return TradingLogger('ai_brain', 'ai_brain.log')


def get_monitor_logger() -> TradingLogger:
    """Get logger for monitoring module"""
    return TradingLogger('monitor', 'monitor.log')

