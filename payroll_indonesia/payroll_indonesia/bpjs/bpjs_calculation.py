"""Utilities for BPJS configuration."""
from types import SimpleNamespace
from typing import Any

from payroll_indonesia.config import config as pi_config

__all__ = ["get_bpjs_settings"]


def get_bpjs_settings() -> Any:
    """Return BPJS settings from :mod:`payroll_indonesia.config.config`.

    The values are loaded via :func:`payroll_indonesia.config.config.get_live_config`
    and returned as a :class:`types.SimpleNamespace` for attribute access.
    """
    cfg = pi_config.get_live_config()
    bpjs_cfg = cfg.get("bpjs", {})
    return SimpleNamespace(**bpjs_cfg)
