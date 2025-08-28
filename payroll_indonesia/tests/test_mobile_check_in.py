import types
import pytest
import frappe

from payroll_indonesia.api.attendance import mobile_check_in


class DummyAttendance:
    def __init__(self):
        self.name = "ATT-001"

    def insert(self, ignore_permissions=True):
        pass


@pytest.fixture(autouse=True)
def setup_common(monkeypatch):
    monkeypatch.setattr(
        frappe, "db", types.SimpleNamespace(get_value=lambda *a, **k: "COMP"), raising=False
    )
    monkeypatch.setattr(frappe, "get_doc", lambda data: DummyAttendance(), raising=False)
    monkeypatch.setattr(frappe, "_", lambda m: m, raising=False)
    monkeypatch.setattr(
        frappe, "PermissionError", type("PermissionError", (Exception,), {}), raising=False
    )
    monkeypatch.setattr(
        frappe,
        "throw",
        lambda msg, exc=None: (_ for _ in ()).throw((exc or Exception)(msg)),
        raising=False,
    )


def test_check_in_within_any_location(monkeypatch):
    settings = types.SimpleNamespace(
        office_locations=[
            types.SimpleNamespace(latitude=0.0, longitude=0.0),
            types.SimpleNamespace(latitude=1.0, longitude=1.0),
        ]
    )
    monkeypatch.setattr(frappe, "get_single", lambda d: settings, raising=False)

    res = mobile_check_in("EMP-001", 1.0, 1.0)
    assert res["message"] == "Attendance marked"


def test_check_in_out_of_range(monkeypatch):
    settings = types.SimpleNamespace(
        office_locations=[
            types.SimpleNamespace(latitude=0.0, longitude=0.0),
            types.SimpleNamespace(latitude=1.0, longitude=1.0),
        ]
    )
    monkeypatch.setattr(frappe, "get_single", lambda d: settings, raising=False)

    with pytest.raises(frappe.PermissionError):
        mobile_check_in("EMP-001", 50.0, 50.0)
