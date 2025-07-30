import frappe
from frappe import ValidationError
from frappe.utils import flt
from payroll_indonesia.utils import round_half_up, sum_bruto_earnings
from payroll_indonesia.config import (
    get_biaya_jabatan_rate,
    get_biaya_jabatan_cap_monthly,
    get_ter_code,
    get_ter_rate,
)

# from payroll_indonesia.utils import round_half_up

def sum_bruto_earnings(salary_slip):
    """
    Sum all earning components contributing to bruto pay (including taxable natura).
    Criteria:
      - is_tax_applicable = 1
      - OR is_income_tax_component = 1
      - OR variable_based_on_taxable_salary = 1
      - do_not_include_in_total = 0
      - statistical_component = 0
      - exempted_from_income_tax = 0 (if field exists)
    """
    total = 0.0
    earnings = salary_slip.get("earnings", [])
    for row in earnings:
        if (
            (row.get("is_tax_applicable", 0) == 1 or
             row.get("is_income_tax_component", 0) == 1 or
             row.get("variable_based_on_taxable_salary", 0) == 1)
            and row.get("do_not_include_in_total", 0) == 0
            and row.get("statistical_component", 0) == 0
            and row.get("exempted_from_income_tax", 0) == 0
        ):
            total += flt(row.get("amount", 0))
    return total

def sum_pengurang_netto(salary_slip):
    """
    Sum deductions that reduce netto (BPJS Employee etc).
    Criteria:
      - is_income_tax_component = 1 OR variable_based_on_taxable_salary = 1
      - do_not_include_in_total = 0
      - statistical_component = 0
      - Exclude 'Biaya Jabatan'
    """
    total = 0.0
    deductions = salary_slip.get("deductions", [])
    for row in deductions:
        if (
            (row.get("is_income_tax_component", 0) == 1 or row.get("variable_based_on_taxable_salary", 0) == 1)
            and row.get("do_not_include_in_total", 0) == 0
            and row.get("statistical_component", 0) == 0
            and "biaya jabatan" not in row.get("salary_component", "").lower()
        ):
            total += flt(row.get("amount", 0))
    return total

def get_biaya_jabatan_from_component(salary_slip):
    """
    Get 'Biaya Jabatan' deduction from salary slip, return 0 if not present.
    """
    deductions = salary_slip.get("deductions", [])
    for row in deductions:
        if "biaya jabatan" in row.get("salary_component", "").lower():
            return flt(row.get("amount", 0))
    return 0.0

def calculate_pph21_TER(employee_doc, salary_slip):
    # 1) Validasi employment type
    emp_type = employee_doc["employment_type"] if isinstance(employee_doc, dict) \
               else employee_doc.employment_type
    if emp_type == " ":
        return {
            "employment_type_checked": False,
            "pph21": 0.0,
            "message": "PPh21 TER hanya untuk Employment Type: Full-time",
        }

    # 2) Hitung bruto
    bruto = sum_bruto_earnings(salary_slip)

    # 3) Biaya jabatan
    bj_rate = get_biaya_jabatan_rate()               # 5 %
    bj_cap  = get_biaya_jabatan_cap_monthly()        # 500 000
    try:
        from payroll_indonesia.utils import get_biaya_jabatan_from_component
        biaya_jabatan = get_biaya_jabatan_from_component(salary_slip) or \
                        min(bruto * bj_rate / 100, bj_cap)
    except ImportError:
        biaya_jabatan = min(bruto * bj_rate / 100, bj_cap)

    # 4) Taxable income dan tarif TER
    taxable_income = bruto - biaya_jabatan
    ter_code = get_ter_code(employee_doc)
    rate = get_ter_rate(ter_code, taxable_income)

    # 5) PPh21
    pph21 = round_half_up(taxable_income * rate / 100)

    return {
        "bruto": bruto,
        "biaya_jabatan": biaya_jabatan,
        "taxable_income": taxable_income,
        "rate": rate,
        "pph21": pph21,
        "employment_type_checked": True,
    }