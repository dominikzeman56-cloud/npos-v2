# neuroman/tools/__init__.py
"""Specialized tool adapters dispatched by NeuroManOrchestrator."""

from .ableton import AbletonController
from .coder import dispatch_to_coder
from .web import handle_web_query
from .cline_bridge import dispatch_to_cline

__all__ = [
    "AbletonController",
    "dispatch_to_coder",
    "handle_web_query",
    "dispatch_to_cline",
]
