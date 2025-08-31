import types
import frappe

from payroll_indonesia.override.payroll_entry import CustomPayrollEntry
from payroll_indonesia.override.salary_slip import CustomSalarySlip


def test_posting_date_sets_period_for_absence_deduction(monkeypatch):
    pe = CustomPayrollEntry()
    pe.posting_date = "2024-03-15"
    pe._ensure_default_period()

    assert pe.start_date == "2024-03-01"
    assert pe.end_date == "2024-03-15"

    slip = CustomSalarySlip()
    slip.name = "SS-TEST"
    slip.employee = "EMP-001"
    slip.company = "COMP"
    slip.start_date = pe.start_date
    slip.end_date = pe.end_date
    slip.base = 3100
    slip.total_working_days = 31
    slip.currency = "IDR"
    slip.earnings = [types.SimpleNamespace(amount=3100)]
    slip.deductions = []
    slip.rounded_total = 0
    slip.total = 0

    captured = {}

    def fake_get_all(doctype, filters=None, fields=None):
        if doctype == "Employee Attendance":
            captured["filters"] = filters
            return []
        return []

    monkeypatch.setattr(frappe, "get_all", fake_get_all)
    monkeypatch.setattr(
        "payroll_indonesia.override.salary_slip.calculate_pph21_TER",
        lambda *a, **k: {"pph21": 0},
    )
    monkeypatch.setattr(CustomSalarySlip, "update_pph21_row", lambda self, tax: None)

    slip.calculate_income_tax()

    assert captured["filters"]["attendance_date"][1] == [pe.start_date, pe.end_date]
