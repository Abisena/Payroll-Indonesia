import sys
import os
import types
import importlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Minimal frappe stub
frappe = types.ModuleType("frappe")
utils_mod = types.ModuleType("frappe.utils")


def flt(val, precision=None):
    return float(val or 0)

utils_mod.flt = flt

class DummyLogger:
    def info(self, msg):
        pass
    def warning(self, msg):
        pass

def logger():
    return DummyLogger()

safe_exec_mod = types.ModuleType("frappe.utils.safe_exec")
safe_exec_mod.safe_eval = lambda expr, context=None: None
frappe.utils = utils_mod
frappe.logger = logger
frappe.as_json = lambda obj: "{}"
frappe.get_cached_doc = lambda *a, **k: {}
frappe.get_value = lambda *a, **k: None

class DummyDB:
    def exists(self, *a, **k):
        return False

frappe.db = DummyDB()
frappe.ValidationError = type("ValidationError", (Exception,), {})
sys.modules.setdefault("frappe.utils.safe_exec", safe_exec_mod)

sys.modules.setdefault("frappe", frappe)
sys.modules.setdefault("frappe.utils", utils_mod)

slip_module = importlib.import_module("payroll_indonesia.override.salary_slip")
slip_module.frappe.as_json = frappe.as_json
CustomSalarySlip = slip_module.CustomSalarySlip


def test_compute_income_tax_sets_fields(monkeypatch):
    monkeypatch.setattr(
        "payroll_indonesia.override.salary_slip.calculate_pph21_TER",
        lambda emp, slip: {"pph21": 123},
    )

    slip = CustomSalarySlip()
    slip.earnings = []
    slip.deductions = []
    slip.get = lambda field, default=None: getattr(slip, field, default)
    import types
    def append(field, value):
        if isinstance(value, dict):
            value = types.SimpleNamespace(**value)
        getattr(slip, field).append(value)
    slip.append = append
    slip.as_dict = lambda: {"earnings": slip.earnings, "deductions": slip.deductions}
    slip.get_employee_doc = lambda: {}
    slip.gross_pay = 0
    slip.total_deduction = 0

    tax = slip.compute_income_tax()

    assert tax == 123
    assert slip.tax == 123
    assert slip.tax_type == "TER"
    assert any(getattr(d, "salary_component", None) == "PPh 21" for d in slip.deductions)

