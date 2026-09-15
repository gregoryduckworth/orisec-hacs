"""Orisec integration package."""

from .const import DOMAIN


async def async_setup(hass, config):
    """Set up the Orisec integration."""
    return True


__all__ = ["DOMAIN", "async_setup"]
