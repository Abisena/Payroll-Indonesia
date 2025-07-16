import sys
import types


def test_take_home_calculator_basic():
    # stub frappe utils with minimal flt function
    frappe = types.ModuleType("frappe")
    frappe.utils = types.ModuleType("frappe.utils")
    frappe.utils.flt = float
    frappe._ = lambda x: x
    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = frappe.utils

    # stub override package to avoid importing payroll_entry
    override_pkg = types.ModuleType("payroll_indonesia.override")
    salary_slip_pkg = types.ModuleType("payroll_indonesia.override.salary_slip")
    salary_slip_pkg.__path__ = []
    override_pkg.salary_slip = salary_slip_pkg
    sys.modules["payroll_indonesia.override"] = override_pkg
    sys.modules["payroll_indonesia.override.salary_slip"] = salary_slip_pkg

    # stub bpjs calculator to avoid full dependency
    bpjs_stub = types.ModuleType("payroll_indonesia.override.salary_slip.bpjs_calculator")

    def simple_calc(base, rate, max_salary=None):
        if max_salary and base > max_salary:
            base = max_salary
        return round(base * rate / 100.0)

    bpjs_stub.calculate_bpjs = simple_calc
    sys.modules[
        "payroll_indonesia.override.salary_slip.bpjs_calculator"
    ] = bpjs_stub

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "take_home_calculator",
        "payroll_indonesia/override/salary_slip/take_home_calculator.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    res = mod.calculate_take_home_and_bpjs(10_000_000)

    assert res["employee_total"] == 390776
    assert res["employer_total"] == 1005552
    assert res["take_home_pay"] == 10_000_000 - 390776
    assert res["taxable_base"] == 10_000_000 - 390776
