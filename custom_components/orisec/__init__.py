"""Orisec integration package."""

from typing import Any

from .const import DOMAIN


async def async_setup(hass: Any, config: dict[str, Any]) -> bool:
    """Set up the Orisec integration."""
    return True


__all__ = ["DOMAIN", "async_setup"]
