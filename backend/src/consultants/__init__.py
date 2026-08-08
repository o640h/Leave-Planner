"""Consultant directory persistence and API."""

from .models import Consultant
from .router import router

__all__ = [
    "Consultant",
    "router",
]
