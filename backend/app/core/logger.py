"""
logger.py
=========
Sistem logging terpusat untuk backend.

Fitur:
  - Log ke console (berwarna) + file (logs/backend.log)
  - Level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - Rotating file handler (max 5MB, 5 backup)
  - Helper get_logger(name) untuk tiap modul
  - Capture full traceback untuk error
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler

LOG_DIR  = os.path.join(os.getcwd(), "logs")
LOG_FILE = os.path.join(LOG_DIR, "backend.log")
os.makedirs(LOG_DIR, exist_ok=True)

DEBUG_MODE = os.getenv("DEBUG", "True").lower() == "true"
LEVEL      = logging.DEBUG if DEBUG_MODE else logging.INFO

# ── ANSI Colors untuk console ───────────────────────────────────────────────
COLORS = {
    "DEBUG":    "\033[36m",   # cyan
    "INFO":     "\033[32m",   # green
    "WARNING":  "\033[33m",   # yellow
    "ERROR":    "\033[31m",   # red
    "CRITICAL": "\033[41m",   # red bg
}
RESET = "\033[0m"


class ColorFormatter(logging.Formatter):
    def format(self, record):
        color = COLORS.get(record.levelname, "")
        record.levelname_colored = f"{color}{record.levelname:<8}{RESET}"
        record.name_short = record.name[-20:]
        return super().format(record)


_console_fmt = ColorFormatter(
    "%(asctime)s | %(levelname_colored)s | %(name_short)-20s | %(message)s",
    datefmt="%H:%M:%S",
)

_file_fmt = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)-25s | %(funcName)s:%(lineno)d | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ── Handlers (dibuat sekali) ────────────────────────────────────────────────
_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(_console_fmt)
_console_handler.setLevel(LEVEL)

_file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_file_handler.setFormatter(_file_fmt)
_file_handler.setLevel(logging.DEBUG)  # file selalu simpan DEBUG

_loggers: dict = {}


def get_logger(name: str) -> logging.Logger:
    """Ambil logger untuk modul tertentu."""
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if not logger.handlers:
        logger.addHandler(_console_handler)
        logger.addHandler(_file_handler)

    _loggers[name] = logger
    return logger


def read_recent_logs(lines: int = 200) -> list:
    """Baca N baris terakhir dari log file (untuk endpoint /debug/logs)."""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        return [l.rstrip("\n") for l in all_lines[-lines:]]
    except Exception:
        return []
