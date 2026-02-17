"""
shared.config
~~~~~~~~~~~~~
Centralised application configuration via Pydantic Settings.
Import `get_settings()` everywhere — never import Settings directly.
"""

from shared.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
