"""Integração Meta Graph API (Instagram + Facebook + Ads + Pixel)."""
from app.integrations.meta.client import MetaGraphClient, MetaGraphError

__all__ = ["MetaGraphClient", "MetaGraphError"]
