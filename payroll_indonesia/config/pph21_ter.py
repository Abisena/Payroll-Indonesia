import frappe
from payroll_indonesia.utils import (
    round_half_up,
    sum_bruto_earnings,
    sum_pengurang_netto,
    get_biaya_jabatan_from_component,
)
from payroll_indonesia.config import (
    get_biaya_jabatan_rate,
    get_biaya_jabatan_cap_monthly,
    get_ter_code,
    get_ter_rate,
    get_ptkp_amount,
)

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
    bj_cap = get_biaya_jabatan_cap_monthly()        # 500 000
    biaya_jabatan = get_biaya_jabatan_from_component(salary_slip)
    if biaya_jabatan is None:
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