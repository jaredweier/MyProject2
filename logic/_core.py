"""
Backward-compat shim — exports and dashboard moved to slice modules.
Prefer importing from logic.exports or logic.dashboard directly.
"""

from logic.dashboard import *
from logic.exports import *
