import sys
import types
import importlib


def test_patch_get_versions_injects_version():
    # create a minimal frappe stub
    frappe = types.ModuleType("frappe")

    def get_versions():
        return {"frappe": "1.0"}

    frappe.get_versions = get_versions
    sys.modules["frappe"] = frappe

    module = importlib.import_module("payroll_indonesia")

    module.patch_get_versions()
    patched = frappe.get_versions

    versions = patched()
    assert versions["frappe"] == "1.0"
    assert versions["payroll_indonesia"] == module.__version__

    # ensure idempotent
    module.patch_get_versions()
    assert frappe.get_versions is patched
    assert frappe.get_versions()["payroll_indonesia"] == module.__version__

    del sys.modules["frappe"]
