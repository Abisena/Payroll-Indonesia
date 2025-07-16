import sys
import types
import pytest

pytest.importorskip("frappe")


def test_payroll_entry_on_submit_sets_status(monkeypatch):
    # minimal frappe stub
    frappe = types.ModuleType("frappe")
    sys.modules["frappe"] = frappe

    # stub frappe.db to avoid errors
    frappe.db = types.SimpleNamespace(set_value=lambda *a, **k: None)

    # minimal Document class to simulate submit behaviour
    model_module = types.ModuleType("frappe.model")
    document_module = types.ModuleType("frappe.model.document")

    class Document:
        def db_set(self, field, value):
            setattr(self, field, value)

        def submit(self):
            if hasattr(self, "before_submit"):
                self.before_submit()
            if hasattr(self, "on_submit"):
                self.on_submit()
            if hasattr(self, "after_submit"):
                self.after_submit()
            self.docstatus = 1

    document_module.Document = Document
    sys.modules["frappe.model"] = model_module
    sys.modules["frappe.model.document"] = document_module

    # stub logger used in module
    logger = types.SimpleNamespace(debug=lambda *a, **k: None, exception=lambda *a, **k: None)
    sys.modules["payroll_indonesia.frappe_helpers"] = types.SimpleNamespace(logger=logger)

    import importlib

    pe_module = importlib.import_module("payroll_indonesia.override.payroll_entry")

    entry = pe_module.CustomPayrollEntry()
    entry.name = "PE-001"
    entry.submit()

    assert getattr(entry, "status", None) == "Submitted"
