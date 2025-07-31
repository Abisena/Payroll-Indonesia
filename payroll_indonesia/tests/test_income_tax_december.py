import sys
import os
import types
import importlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Frappe stub ---------------------------------------------------------------
frappe = types.ModuleType("frappe")
utils_mod = types.ModuleType("frappe.utils")
safe_exec_mod = types.ModuleType("frappe.utils.safe_exec")


def flt(val, precision=None):
    return float(val)


def safe_eval(expr, context=None):
    return eval(expr, context or {})


class DummyLogger:
    def info(self, msg):
        pass

    def warning(self, msg):
        pass


def logger():
    return DummyLogger()


frappe.utils = utils_mod
frappe.logger = logger
frappe.get_cached_doc = lambda *args, **kwargs: {}
frappe.ValidationError = type("ValidationError", (Exception,), {})
utils_mod.flt = flt
utils_mod.safe_exec = safe_exec_mod
safe_exec_mod.safe_eval = safe_eval
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = utils_mod
sys.modules["frappe.utils.safe_exec"] = safe_exec_mod

# Module imports ------------------------------------------------------------
salary_slip_module = importlib.import_module("payroll_indonesia.override.salary_slip")
CustomSalarySlip = salary_slip_module.CustomSalarySlip
pph21_ter_december = importlib.import_module("payroll_indonesia.config.pph21_ter_december")


# Test ---------------------------------------------------------------------
def test_december_calc_uses_previous_months(monkeypatch):
    slips_db = {
        "SS1": {"earnings": [], "deductions": [], "month": 1, "tax": 50},
        "SS2": {"earnings": [], "deductions": [], "month": 2, "tax": 70},
    }

    def get_all(doctype, filters=None, pluck=None):
        assert doctype == "Salary Slip"
        return list(slips_db.keys())

    def get_doc(doctype, name):
        assert doctype == "Salary Slip"
        return slips_db[name]

    frappe.get_all = get_all
    frappe.get_doc = get_doc

    captured = {}

    def fake_calc(employee_doc, slips, pph21_paid_jan_nov=0):
        captured["count"] = len(slips)
        captured["paid"] = pph21_paid_jan_nov
        return {"pph21_month": 0}

    monkeypatch.setattr(pph21_ter_december, "calculate_pph21_TER_december", fake_calc)

    def _init(self, **data):
        for k, v in data.items():
            setattr(self, k, v)
        if not hasattr(self, "earnings"):
            self.earnings = []
        if not hasattr(self, "deductions"):
            self.deductions = []
        if not hasattr(self, "gross_pay"):
            self.gross_pay = 0

    def append(self, table_field, row):
        getattr(self, table_field).append(row)

    def sync_to_annual_payroll_history(self, result, mode="monthly"):
        pass

    monkeypatch.setattr(CustomSalarySlip, "__init__", _init, raising=False)
    monkeypatch.setattr(CustomSalarySlip, "append", append, raising=False)
    monkeypatch.setattr(CustomSalarySlip, "sync_to_annual_payroll_history", sync_to_annual_payroll_history, raising=False)

    slip = CustomSalarySlip(
        employee={"name": "EMP-1", "employment_type": "Full-time", "tax_status": "TK/0"},
        fiscal_year="2023",
        month=12,
        earnings=[],
        deductions=[],
    )

    slip.calculate_income_tax_december()

    assert captured["count"] == 3
    assert captured["paid"] == 120

    # cleanup modules so other tests import fresh versions
    for mod in [
        "frappe",
        "frappe.utils",
        "frappe.utils.safe_exec",
        "payroll_indonesia.override.salary_slip",
        "payroll_indonesia.config.pph21_ter_december",
    ]:
        sys.modules.pop(mod, None)
