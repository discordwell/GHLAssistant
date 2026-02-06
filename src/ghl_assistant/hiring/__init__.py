"""Hiring funnel setup and management."""

from .guide import render_setup_guide
from .template import get_hiring_blueprint

__all__ = ["get_hiring_blueprint", "render_setup_guide"]
