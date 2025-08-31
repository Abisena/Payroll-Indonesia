import types
import pytest
import frappe

from payroll_indonesia.override.salary_slip import CustomSalarySlip


@pytest.mark.parametrize("status", ["Absent"])
def test_absence_deduction(monkeypatch, status):
    slip = CustomSalarySlip()
    slip.name = "SS-TEST"
    slip.employee = "EMP-001"
    slip.company = "COMP"
    slip.start_date = "2024-01-01"
    slip.end_date = "2024-01-31"
    slip.base = 3100
    slip.total_working_days = 31
    slip.currency = "IDR"
    slip.earnings = [types.SimpleNamespace(amount=3100)]
    slip.deductions = []
    slip.rounded_total = 0
    slip.total = 0

    monkeypatch.setattr(frappe, "get_all", lambda *a, **k: [{"status": status}])
    monkeypatch.setattr(
        "payroll_indonesia.override.salary_slip.calculate_pph21_TER",
        lambda *a, **k: {"pph21": 0},
    )
    monkeypatch.setattr(CustomSalarySlip, "update_pph21_row", lambda self, tax: None)

    slip.calculate_income_tax()

    deduction = [
        d
        for d in slip.deductions
        if (d.get("salary_component") if isinstance(d, dict) else getattr(d, "salary_component", None))
        == "Absence Deduction"
    ]
    assert deduction, "Absence deduction row not found"
    amount = deduction[0]["amount"] if isinstance(deduction[0], dict) else deduction[0].amount
    assert amount == pytest.approx(100.0)

