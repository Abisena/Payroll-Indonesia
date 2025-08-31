import types

import frappe

# Ensure required frappe utilities exist before importing module under test
frappe._ = lambda msg: msg
frappe.utils.today = lambda: "2024-01-01"
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.get_single = lambda *a, **k: None

from payroll_indonesia.api.attendance import mobile_check_in


def test_mobile_check_in_work_from_home(monkeypatch):
    """mobile_check_in should accept Work From Home status"""

    # Stub configuration and db functions
    monkeypatch.setattr(
        frappe,
        "get_single",
        lambda name: types.SimpleNamespace(office_latitude=0.0, office_longitude=0.0),
    )
    monkeypatch.setattr(frappe.db, "get_value", lambda *a, **k: "Test Company")

    inserted = {}

    class DummyDoc:
        def __init__(self, data):
            self.data = data
            self.name = "ATT-0001"

        def insert(self, ignore_permissions=False):
            inserted.update(self.data)

    monkeypatch.setattr(frappe, "get_doc", lambda data: DummyDoc(data))

    result = mobile_check_in("EMP-0001", 0.0, 0.0, status="Work From Home")

    assert inserted["status"] == "Work From Home"
    assert result["name"] == "ATT-0001"


def test_mobile_check_in_default_status(monkeypatch):
    monkeypatch.setattr(
        frappe,
        "get_single",
        lambda name: types.SimpleNamespace(office_latitude=0.0, office_longitude=0.0),
    )
    monkeypatch.setattr(frappe.db, "get_value", lambda *a, **k: "Test Company")

    captured = {}

    class DummyDoc:
        def __init__(self, data):
            self.data = data
            self.name = "ATT-0002"

        def insert(self, ignore_permissions=False):
            captured.update(self.data)

    monkeypatch.setattr(frappe, "get_doc", lambda data: DummyDoc(data))

    result = mobile_check_in("EMP-0001", 0.0, 0.0)

    assert captured["status"] == "Present"
    assert result["name"] == "ATT-0002"
