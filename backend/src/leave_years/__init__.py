"""Consultant leave-year persistence and API."""

from .models import LeaveYear
from .router import router

__all__ = [
    "LeaveYear",
    "router",
]
