"""Custom Salary Slip override for Payroll Indonesia.

Adds Indonesian income tax logic and patches ``eval_condition_and_formula`` so
that helper functions defined in ``hooks.salary_slip_globals`` are available when
evaluating Salary Component formulas.
"""

try:
    from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip
except Exception:  # pragma: no cover - erpnext may not be installed during tests
    SalarySlip = object  # type: ignore

import frappe

from payroll_indonesia.config import pph21_ter, pph21_ter_december
from payroll_indonesia.utils import sync_annual_payroll_history
from frappe.utils.safe_exec import safe_eval
from payroll_indonesia import _patch_salary_slip_globals

class CustomSalarySlip(SalarySlip):
    """
    Salary Slip with Indonesian income tax calculations (TER bulanan dan Progressive/Desember).
    Koreksi PPh21 minus: PPh21 di slip minus, THP otomatis bertambah oleh sistem.
    Sinkronisasi ke Annual Payroll History setiap kali slip dihitung atau dibatalkan.
    """

    def eval_condition_and_formula(self, struct_row, data):
        """Evaluate condition and formula with additional Payroll Indonesia globals."""
        context = data.copy()
        context.update(_patch_salary_slip_globals())

        try:
            if getattr(struct_row, "condition", None):
                if not safe_eval(struct_row.condition, context):
                    return 0

            if getattr(struct_row, "formula", None):
                return safe_eval(struct_row.formula, context)
        except Exception as e:
            frappe.throw(f"Failed evaluating formula for {getattr(struct_row, 'salary_component', 'component')}: {e}")

        return super().eval_condition_and_formula(struct_row, data)

    def calculate_income_tax(self):
        """
        Hitung pajak penghasilan sesuai mode payroll (TER atau Progressive/Desember).
        Koreksi PPh21 minus: komponen pajak di slip akan minus, THP otomatis bertambah.
        Sinkronisasi ke Annual Payroll History.
        """
        # Mode: Progressive/Desember (final year/progressive)
        if getattr(self, "run_payroll_indonesia_december", False):
            frappe.logger().info("Salary Slip: calculating PPh21 December (progressive) mode.")
            employee_doc = self.get_employee_doc()
            salary_slips = getattr(self, "salary_slips_this_year", [self])
            pph21_paid_jan_nov = getattr(self, "pph21_paid_jan_nov", 0)

            result = pph21_ter_december.calculate_pph21_TER_december(
                employee_doc,
                salary_slips,
                pph21_paid_jan_nov=pph21_paid_jan_nov
            )
            self.pph21_info = result
            koreksi_pph21 = result.get("koreksi_pph21", 0)
            self.tax = koreksi_pph21
            self.tax_type = "DECEMBER"
            self.sync_to_annual_payroll_history(result, mode="december")
            return self.tax

        # Mode: TER (bulanan/flat)
        if getattr(self, "run_payroll_indonesia", False):
            frappe.logger().info("Salary Slip: calculating PPh21 TER mode.")
            employee_doc = self.get_employee_doc()
            result = pph21_ter.calculate_pph21_TER(employee_doc, self)
            self.pph21_info = result
            self.tax = result.get("pph21", 0)
            self.tax_type = "TER"
            self.sync_to_annual_payroll_history(result, mode="monthly")
            return self.tax

        # Default: fallback to vanilla ERPNext
        return super().calculate_income_tax()

    def get_employee_doc(self):
        """
        Helper: get employee doc/dict from self.employee (id, dict, or object).
        """
        if hasattr(self, "employee"):
            emp = self.employee
            if isinstance(emp, dict):
                return emp
            try:
                return frappe.get_doc("Employee", emp)
            except Exception:
                return {}
        return {}

    def as_dict(self):
        """
        Return a dict representation (for compatibility with PayrollEntry batch logic).
        """
        doc = super().as_dict() if hasattr(super(), "as_dict") else dict(self.__dict__)
        doc.update({
            "pph21_info": getattr(self, "pph21_info", {}),
            "tax": getattr(self, "tax", 0),
            "tax_type": getattr(self, "tax_type", None)
        })
        return doc

    def sync_to_annual_payroll_history(self, result, mode="monthly"):
        """
        Sinkronisasi hasil slip ke Annual Payroll History.
        Untuk mode 'monthly': hanya satu bulan.
        Untuk mode 'december': bisa summary full year.
        """
        try:
            employee_doc = self.get_employee_doc()
            fiscal_year = getattr(self, "fiscal_year", None) or str(getattr(self, "start_date", ""))[:4]
            if not fiscal_year:
                return

            monthly_result = {
                "bulan": getattr(self, "month", None) or getattr(self, "bulan", None),
                "bruto": result.get("bruto", result.get("bruto_total", 0)),
                "pengurang_netto": result.get("pengurang_netto", result.get("income_tax_deduction_total", 0)),
                "biaya_jabatan": result.get("biaya_jabatan", result.get("biaya_jabatan_total", 0)),
                "netto": result.get("netto", result.get("netto_total", 0)),
                "pkp": result.get("pkp", result.get("pkp_annual", 0)),
                "rate": result.get("rate", ""),
                "pph21": result.get("pph21", result.get("pph21_month", 0)),
                "salary_slip": self.name,
            }
            if mode == "monthly":
                sync_annual_payroll_history.sync_annual_payroll_history(
                    employee=employee_doc,
                    fiscal_year=fiscal_year,
                    monthly_results=[monthly_result],
                    summary=None
                )
            elif mode == "december":
                summary = {
                    "bruto_total": result.get("bruto_total", 0),
                    "netto_total": result.get("netto_total", 0),
                    "ptkp_annual": result.get("ptkp_annual", 0),
                    "pkp_annual": result.get("pkp_annual", 0),
                    "pph21_annual": result.get("pph21_annual", 0),
                    "koreksi_pph21": result.get("koreksi_pph21", 0),
                }
                sync_annual_payroll_history.sync_annual_payroll_history(
                    employee=employee_doc,
                    fiscal_year=fiscal_year,
                    monthly_results=[monthly_result],
                    summary=summary
                )
        except Exception as e:
            frappe.logger().error(f"Failed to sync Annual Payroll History: {e}")

    def on_cancel(self):
        """
        Saat slip dibatalkan, hapus baris terkait di Annual Payroll History.
        """
        try:
            employee_doc = self.get_employee_doc()
            fiscal_year = getattr(self, "fiscal_year", None) or str(getattr(self, "start_date", ""))[:4]
            if not fiscal_year:
                return
            sync_annual_payroll_history.sync_annual_payroll_history(
                employee=employee_doc,
                fiscal_year=fiscal_year,
                monthly_results=None,
                summary=None,
                cancelled_salary_slip=self.name
            )
        except Exception as e:
            frappe.logger().error(f"Failed to remove from Annual Payroll History on cancel: {e}")
