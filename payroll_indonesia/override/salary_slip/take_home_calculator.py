# -*- coding: utf-8 -*-
"""Utility to compute BPJS deductions, employer contributions and take-home pay."""

from typing import Dict, Any

from frappe.utils import flt

from payroll_indonesia.override.salary_slip.bpjs_calculator import calculate_bpjs
from payroll_indonesia.constants import DEFAULT_BPJS_RATES

__all__ = ["calculate_take_home_and_bpjs"]


def calculate_take_home_and_bpjs(
    gross_salary: float,
    bpjs_rates: Dict[str, Any] | None = None,
) -> Dict[str, float]:
    """Return totals for BPJS and take-home pay given salary and rate settings."""
    try:
        rates = {**DEFAULT_BPJS_RATES}
        if bpjs_rates:
            rates.update({k: flt(v) for k, v in bpjs_rates.items() if v is not None})

        base = flt(gross_salary)
        # Employee portions
        kes_emp = calculate_bpjs(
            base,
            rates["kesehatan_employee_percent"],
            max_salary=rates.get("kesehatan_max_salary"),
        )
        jht_emp = calculate_bpjs(base, rates["jht_employee_percent"])
        jp_emp = calculate_bpjs(
            base,
            rates["jp_employee_percent"],
            max_salary=rates.get("jp_max_salary"),
        )

        # Employer portions
        kes_com = calculate_bpjs(
            base,
            rates["kesehatan_employer_percent"],
            max_salary=rates.get("kesehatan_max_salary"),
        )
        jht_com = calculate_bpjs(base, rates["jht_employer_percent"])
        jp_com = calculate_bpjs(
            base,
            rates["jp_employer_percent"],
            max_salary=rates.get("jp_max_salary"),
        )
        jkk = calculate_bpjs(base, rates["jkk_percent"])
        jkm = calculate_bpjs(base, rates["jkm_percent"])

        employee_total = kes_emp + jht_emp + jp_emp
        employer_total = kes_com + jht_com + jp_com + jkk + jkm

        take_home = base - employee_total
        taxable_base = base - employee_total

        return {
            "employee_total": float(employee_total),
            "employer_total": float(employer_total),
            "take_home_pay": float(take_home),
            "taxable_base": float(taxable_base),
            "kesehatan_employee": float(kes_emp),
            "jht_employee": float(jht_emp),
            "jp_employee": float(jp_emp),
            "kesehatan_employer": float(kes_com),
            "jht_employer": float(jht_com),
            "jp_employer": float(jp_com),
            "jkk": float(jkk),
            "jkm": float(jkm),
        }
    except Exception:
        return {
            "employee_total": 0.0,
            "employer_total": 0.0,
            "take_home_pay": 0.0,
            "taxable_base": 0.0,
        }
