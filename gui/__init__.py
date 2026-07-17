"""Chronos Command — modern web + native NiceGUI frontend.

Primary entry: `from gui.app import run` or `python main.py`.
Business rules remain in `logic/*` and `validators.py`.
"""

from gui.app import run

__all__ = ["run"]
