"""Utility helpers for payroll indonesia."""

from decimal import Decimal, ROUND_HALF_UP

from frappe.utils import flt

__all__ = ["round_half_up", "sum_bruto_earnings", "get_biaya_jabatan_from_component"]


def round_half_up(value: float) -> int:
    """Round value to nearest integer using the HALF_UP rule."""
    return int(Decimal(str(value)).quantize(0, rounding=ROUND_HALF_UP))

def sum_bruto_earnings(salary_slip):
    """
    Jumlahkan semua komponen earning yang masuk bruto (termasuk natura taxable).

    Kriteria:
      - is_tax_applicable = 1
      - OR is_income_tax_component = 1
      - OR variable_based_on_taxable_salary = 1
      - do_not_include_in_total = 0
      - statistical_component = 0
      - exempted_from_income_tax = 0 (jika field ada)
    """
    total = 0.0
    for row in salary_slip.get("earnings", []):
        if (
            (row.get("is_tax_applicable", 0) == 1
             or row.get("is_income_tax_component", 0) == 1
             or row.get("variable_based_on_taxable_salary", 0) == 1)
            and row.get("do_not_include_in_total", 0) == 0
            and row.get("statistical_component", 0) == 0
            and row.get("exempted_from_income_tax", 0) == 0
        ):
            total += flt(row.get("amount", 0))
    return total

def get_biaya_jabatan_from_component(slip_doc_or_dict):
    """
    Periksa tab Earnings & Deductions untuk komponen bernama 'Biaya Jabatan'.
    Jika ditemukan, kembalikan jumlahnya (float). Jika tidak, return None.

    slip_doc_or_dict : bisa berupa Document Salary Slip atau dict as_dict().
    """
    if not slip_doc_or_dict:
        return None

    # handle Document vs dict
    earnings = (
        slip_doc_or_dict.get("earnings", [])
        if isinstance(slip_doc_or_dict, dict)
        else slip_doc_or_dict.earnings
    )
    deductions = (
        slip_doc_or_dict.get("deductions", [])
        if isinstance(slip_doc_or_dict, dict)
        else slip_doc_or_dict.deductions
    )

    # cari di Earnings dulu (jika Anda jadikan komponen earning)
    for row in earnings:
        if (row.get("salary_component") or getattr(row, "salary_component", "")) == "Biaya Jabatan":
            return flt(row.get("amount") or getattr(row, "amount", 0))

    # lalu cari di Deductions (jika Anda jadikan deduction)
    for row in deductions:
        if (row.get("salary_component") or getattr(row, "salary_component", "")) == "Biaya Jabatan":
            return flt(row.get("amount") or getattr(row, "amount", 0))

    return None  # tidak ditemukan
