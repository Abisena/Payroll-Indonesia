"""Top level package for Payroll Indonesia."""

__version__ = "0.1.0"

__all__ = ["patch_get_versions"]


def patch_get_versions() -> None:
    """Patch ``frappe.get_versions`` to include this package's version.

    The original :func:`frappe.get_versions` returns a mapping of installed app
    names to their versions.  This helper wraps that function so the returned
    mapping always contains ``{"payroll_indonesia": __version__}``.
    """

    try:
        import frappe
    except Exception:  # pragma: no cover - frappe isn't installed during tests
        return

    if getattr(frappe.get_versions, "_patched_for_payroll_indonesia", False):
        return

    original = frappe.get_versions

    def _wrapped_get_versions(*args, **kwargs):
        versions = original(*args, **kwargs)
        if isinstance(versions, dict):
            versions.setdefault("payroll_indonesia", __version__)
        return versions

    _wrapped_get_versions._patched_for_payroll_indonesia = True  # type: ignore[attr-defined]
    frappe.get_versions = _wrapped_get_versions

