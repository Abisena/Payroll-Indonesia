# payroll_indonesia/override/salary_slip.py
"""
Custom Salary Slip override for Payroll Indonesia.

- TER (bulanan) & Progressive (Desember/annual correction).
- Flow Desember (sesuai arahan):
  * Jan–Nov diambil dari Annual Payroll History (APH).
  * Desember dihitung dari slip aktif (bruto, pengurang netto bulanan, biaya jabatan bulanan).
  * Tahunan = (Jan–Nov APH) + (Desember dari slip).
  * PPh Desember (koreksi) = PPh tahunan − total PPh Jan–Nov (APH).
- Selalu menulis baris "PPh 21" di deductions dan sinkron dengan UI.
- Mendukung policy: auto / force_annual / force_monthly.
"""

try:
    from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip
except ImportError:
    from frappe.model.document import Document
    SalarySlip = Document
    import frappe
    frappe.log_error(
        message="Failed to import SalarySlip from hrms.payroll. Using Document fallback.",
        title="Payroll Indonesia Import Warning",
    )

import json
import traceback
import frappe
from frappe.utils import flt
try:
    from frappe.utils import getdate
except Exception:  # pragma: no cover
    from datetime import datetime
    def getdate(value):
        return datetime.strptime(str(value), "%Y-%m-%d")

from frappe.utils.safe_exec import safe_eval

# Hitung PPh
from payroll_indonesia.config.pph21_ter import calculate_pph21_TER
from payroll_indonesia.config.pph21_ter_december import (
    calculate_pph21_december,        # annual correction (desember-only)
    calculate_pph21_desember,        # wrapper: auto/force_annual/force_monthly
    sum_bruto_earnings,               # ambil bruto taxable slip ini (Desember)
    sum_pengurang_netto_bulanan,      # pengurang netto bulanan (exclude Biaya Jabatan)
    biaya_jabatan_bulanan,            # min(5% × bruto_bulan, 500.000)
)

# Sinkronisasi Annual Payroll History
from payroll_indonesia.utils.sync_annual_payroll_history import sync_annual_payroll_history
from payroll_indonesia import _patch_salary_slip_globals

logger = frappe.logger("payroll_indonesia")


class CustomSalarySlip(SalarySlip):
    """Salary Slip override dengan logika PPh21 Indonesia."""

    # -------------------------
    # Helpers umum
    # -------------------------
    def _get_bulan_number(self, start_date=None, nama_bulan=None):
        bulan = None
        if start_date:
            try:
                bulan = getdate(start_date).month
            except Exception:
                logger.debug(f"Gagal parsing start_date: {start_date}")

        if not bulan and nama_bulan:
            peta = {
                "january": 1, "jan": 1, "januari": 1,
                "february": 2, "feb": 2, "februari": 2,
                "march": 3, "mar": 3, "maret": 3,
                "april": 4, "apr": 4,  # <<— alias tambahan
                "may": 5, "mei": 5,
                "june": 6, "jun": 6, "juni": 6,
                "july": 7, "jul": 7, "juli": 7,
                "august": 8, "aug": 8, "agustus": 8,
                "september": 9, "sep": 9,
                "october": 10, "oct": 10, "oktober": 10,
                "november": 11, "nov": 11,
                "december": 12, "dec": 12, "desember": 12,
            }
            bulan = peta.get(str(nama_bulan).strip().lower())

        if not bulan:
            from datetime import datetime
            bulan = datetime.now().month
        return bulan

    def get_employee_doc(self):
        if hasattr(self, "employee"):
            emp = self.employee
            if isinstance(emp, dict):
                return emp
            try:
                return frappe.get_doc("Employee", emp)
            except frappe.DoesNotExistError:
                frappe.log_error(
                    message=f"Employee '{emp}' not found for Salary Slip {self.name}",
                    title="Payroll Indonesia Missing Employee Error",
                )
                raise frappe.ValidationError(f"Employee '{emp}' not found.")
        return {}

    # -------------------------
    # Absence deduction
    # -------------------------
    def _get_unpaid_absent_days(self) -> float:
        """Count attendance records that should result in salary deduction.

        Supports half-day deductions by returning a float. The following
        statuses are considered:

        * ``Absent`` – full day (1.0)
        * ``Half Day`` – half day (0.5)
        * ``Izin``, ``Sakit`` and ``Tanpa Keterangan`` – full day (1.0)
        * ``On Leave`` and ``Work From Home`` – paid (0.0)
        """
        try:
            if not (getattr(self, "employee", None) and getattr(self, "start_date", None) and getattr(self, "end_date", None)):
                return 0.0
            rows = frappe.get_all(
                "Employee Attendance",
                filters={
                    "employee": self.employee,
                    "attendance_date": ["between", [self.start_date, self.end_date]],
                    "docstatus": 1,
                },
                fields=["status"],
            )

            full_day = {"Izin", "Sakit", "Tanpa Keterangan", "Absent"}
            half_day = {"Half Day"}
            days = 0.0
            for r in rows:
                status = r.get("status")
                if status in full_day:
                    days += 1.0
                elif status in half_day:
                    days += 0.5
            return days

        except Exception:
            return 0.0

    def _insert_absence_deduction(self):
        days = self._get_unpaid_absent_days()
        if not days:
            return
        try:
            daily_rate = flt(getattr(self, "base", 0)) / flt(getattr(self, "total_working_days", 1) or 1)
        except Exception:
            daily_rate = 0
        amount = flt(days) * daily_rate
        if not getattr(self, "deductions", None):
            self.deductions = []
        self.deductions.append(frappe._dict({"salary_component": "Absence Deduction", "amount": amount}))
        try:
            self._manual_totals_calculation()
        except Exception:
            pass

    # -------------------------
    # Policy resolver (Auto / Force Annual / Force Monthly)
    # -------------------------
    def _effective_december_policy(self) -> str:
        """Kembalikan policy efektif untuk kalkulasi Desember.
        Urutan prioritas:
        1) Per-slip override via field (checkbox) jika tersedia.
        2) Runtime override via flags (doc.flags.december_policy_override).
        3) Settings (Payroll Indonesia Settings.decem…_partial_year_policy) bila ada.
        4) Default: "auto".
        """
        # 1) Per-slip field override (jika kamu menambahkan field ini ke doctype Salary Slip)
        if getattr(self, "force_annual_december", 0):
            return "force_annual"
        if getattr(self, "force_monthly_december", 0):
            return "force_monthly"

        # 2) Runtime flags override (tanpa ubah schema)
        try:
            val = (getattr(self, "flags", {}) or {}).get("december_policy_override")
            val = (val or "").lower()
            if val in {"auto", "force_annual", "force_monthly"}:
                return val
        except Exception:
            pass

        # 3) Settings (aman meski field belum ada)
        try:
            meta = frappe.get_meta("Payroll Indonesia Settings")
            if meta and hasattr(meta, "has_field") and meta.has_field("december_partial_year_policy"):
                val = frappe.db.get_single_value("Payroll Indonesia Settings", "december_partial_year_policy")
                if val:
                    return val.lower()
        except Exception:
            pass

        return "auto"

    # -------------------------
    # Evaluasi formula
    # -------------------------
    def eval_condition_and_formula(self, struct_row, data):
        context = data.copy()
        context.update(_patch_salary_slip_globals())

        ssa = getattr(self, "salary_structure_assignment", None)
        for f in ("meal_allowance", "transport_allowance"):
            v = getattr(self, f, None)
            if v is None and ssa:
                v = ssa.get(f) if isinstance(ssa, dict) else getattr(ssa, f, None)
            if v is not None:
                context[f] = v

        try:
            if getattr(struct_row, "condition", None):
                if not safe_eval(struct_row.condition, context):
                    return 0
            if getattr(struct_row, "formula", None):
                return safe_eval(struct_row.formula, context)
        except Exception as e:
            frappe.throw(
                f"Failed evaluating formula for {getattr(struct_row, 'salary_component', 'component')}: {e}"
            )

        return super().eval_condition_and_formula(struct_row, data)

    # -------------------------
    # PPh 21 TER (bulanan)
    # -------------------------
    def calculate_income_tax(self):
        try:
            if not getattr(self, "employee", None):
                frappe.throw("Employee data is required for PPh21 calculation", title="Missing Employee")
            if not getattr(self, "company", None):
                frappe.throw("Company is required for PPh21 calculation", title="Missing Company")

            employee_doc = self.get_employee_doc()
            bulan = self._get_bulan_number(
                start_date=getattr(self, "start_date", None),
                nama_bulan=getattr(self, "bulan", None),
            )
            self._insert_absence_deduction()
            taxable_income = self._calculate_taxable_income()

            result = calculate_pph21_TER(
                taxable_income=taxable_income, employee=employee_doc, company=self.company, bulan=bulan
            )
            tax_amount = flt(result.get("pph21", 0.0))

            self.tax = tax_amount
            try:
                self.tax_type = "TER"
            except AttributeError:
                result["_tax_type"] = "TER"

            self.pph21_info = json.dumps(result)
            self.update_pph21_row(tax_amount)
            return tax_amount

        except frappe.ValidationError:
            raise
        except Exception as e:
            frappe.log_error(
                message=f"Failed to calculate income tax (TER): {e}\n{traceback.format_exc()}",
                title=f"Payroll Indonesia TER Calculation Error - {self.name}",
            )
            raise frappe.ValidationError(f"Error in PPh21 calculation: {e}")

    # -------------------------
    # Helper: ambil YTD Jan–Nov dari APH
    # -------------------------
    def _get_ytd_from_aph(self):
        """
        Kembalikan (ytd_bruto_jan_nov, ytd_netto_jan_nov, ytd_tax_paid_jan_nov)
        yang diambil dari Annual Payroll History (monthly_details bulan < 12).
        """
        ytd_bruto = 0.0
        ytd_netto = 0.0
        ytd_tax   = 0.0

        fiscal_year = getattr(self, "fiscal_year", None)
        if not fiscal_year and getattr(self, "start_date", None):
            fiscal_year = str(getdate(self.start_date).year)
        if not fiscal_year:
            return ytd_bruto, ytd_netto, ytd_tax

        try:
            rows = frappe.get_all(
                "Annual Payroll History",
                filters={"employee": self.employee, "fiscal_year": fiscal_year},
                fields=["name"],
                limit=1,
            )
            if rows:
                hist = frappe.get_doc("Annual Payroll History", rows[0].name)
                for r in hist.get("monthly_details", []) or []:
                    bln = getattr(r, "bulan", 0)
                    if bln and bln < 12:
                        ytd_bruto += flt(getattr(r, "bruto", 0))
                        # gunakan kolom netto jika tersedia; fallback: bruto - biaya_jabatan - pengurang_netto
                        r_netto = flt(getattr(r, "netto", 0))
                        if not r_netto:
                            r_netto = flt(getattr(r, "bruto", 0)) \
                                      - flt(getattr(r, "biaya_jabatan", 0)) \
                                      - flt(getattr(r, "pengurang_netto", 0))
                        ytd_netto += r_netto
                        ytd_tax   += flt(getattr(r, "pph21", 0))
        except Exception as e:
            logger.warning(f"Error fetching YTD from Annual Payroll History: {e}")

        return ytd_bruto, ytd_netto, ytd_tax

    # -------------------------
    # Ambil slip setahun (untuk auto/override
    # -------------------------
    def _get_salary_slips_for_year(self):
        fiscal_year = getattr(self, "fiscal_year", None)
        if not fiscal_year and getattr(self, "start_date", None):
            fiscal_year = str(getdate(self.start_date).year)
        if not fiscal_year:
            return []
        try:
            rows = frappe.get_all(
                "Salary Slip",
                filters={"employee": self.employee, "fiscal_year": fiscal_year},
                fields=["name", "start_date", "posting_date", "gross_pay", "income_tax_deduction"],
                order_by="start_date asc",
            )
            slips = []
            for r in rows:
                doc = frappe.get_doc("Salary Slip", r.name)
                slips.append(doc.as_dict())
            return slips
        except Exception as e:
            logger.warning(f"Failed fetching salary slips for year {fiscal_year}: {e}")
            return []

    # -------------------------
    # PPh 21 Progressive (Desember)
    # -------------------------
    def calculate_income_tax_december(self):
        """Hitung PPh21 Desember:
        - Auto: partial-year -> TER bulanan; full-year -> annual correction
        - Force Annual: selalu annual correction
        - Force Monthly: selalu TER bulanan
        """
        try:
            if not getattr(self, "employee", None):
                frappe.throw("Employee data is required for PPh21 calculation", title="Missing Employee")
            if not getattr(self, "company", None):
                frappe.throw("Company is required for PPh21 calculation", title="Missing Company")

            employee_doc = self.get_employee_doc()

            # 1) Ambil YTD Jan–Nov dari APH (untuk display & koreksi saat annual)
            ytd_bruto_jan_nov, ytd_netto_jan_nov, ytd_tax_paid_jan_nov = self._get_ytd_from_aph()

            # 2) Data Desember dari slip aktif
            try:
                slip_dict = self.as_dict()
            except Exception:
                try:
                    slip_dict = self.__dict__.copy()
                except Exception:
                    slip_dict = {}
            bruto_desember = sum_bruto_earnings(slip_dict)
            pengurang_netto_desember = sum_pengurang_netto_bulanan(slip_dict)
            biaya_jabatan_desember = biaya_jabatan_bulanan(bruto_desember)

            # JP+JHT (EE) bulan Desember untuk display/annual (opsional)
            jp_jht_employee_month = 0.0
            for d in (slip_dict.get("deductions") or []):
                name = (d.get("salary_component") or "").strip().lower()
                if name in {"bpjs jht employee", "bpjs jp employee"}:
                    jp_jht_employee_month += flt(d.get("amount", 0))

            # Legacy path: some callers expect old signature
            try:
                legacy = calculate_pph21_december(
                    taxable_income=bruto_desember,
                    employee=employee_doc,
                    company=self.company,
                    ytd_income=ytd_bruto_jan_nov,
                    ytd_tax_paid=ytd_tax_paid_jan_nov,
                )
                if isinstance(legacy, dict) and "pph21_bulan" in legacy:
                    tax_amount = flt(legacy.get("pph21_bulan", 0.0))
                    self.tax = tax_amount
                    try:
                        self.tax_type = "DECEMBER"
                    except AttributeError:
                        legacy["_tax_type"] = "DECEMBER"
                    self.pph21_info = json.dumps(legacy)
                    self.update_pph21_row(tax_amount)
                    return tax_amount
            except TypeError:
                pass

            # 3) Policy efektif (auto/force_annual/force_monthly)
            policy = self._effective_december_policy()

            # 4) Siapkan daftar slip tahun berjalan untuk deteksi partial-year (Auto)
            try:
                year_slips = self._get_salary_slips_for_year()
            except Exception:
                year_slips = []
            # pastikan slip saat ini ikut dihitung jika belum ada di DB
            try:
                year_slips = list(year_slips or [])
                year_slips.append({
                    "start_date": getattr(self, "start_date", None),
                    "posting_date": getattr(self, "posting_date", None),
                    "gross_pay": getattr(self, "gross_pay", 0),
                    "income_tax_deduction": getattr(self, "tax", 0),
                    "earnings": getattr(self, "earnings", []) or [],
                    "deductions": getattr(self, "deductions", []) or [],
                })
            except Exception:
                pass

            # 5) Jika force_annual -> langsung hitung annual correction dengan YTD APH
            if policy == "force_annual":
                try:
                    res = calculate_pph21_december(
                        employee=employee_doc,
                        company=self.company,
                        ytd_bruto_jan_nov=ytd_bruto_jan_nov,
                        ytd_netto_jan_nov=ytd_netto_jan_nov,
                        ytd_tax_paid_jan_nov=ytd_tax_paid_jan_nov,
                        bruto_desember=bruto_desember,
                        pengurang_netto_desember=pengurang_netto_desember,   # display only
                        biaya_jabatan_desember=biaya_jabatan_desember,
                        jp_jht_employee_month=jp_jht_employee_month,
                    )
                except TypeError:
                    res = calculate_pph21_december(
                        taxable_income=bruto_desember,
                        employee=employee_doc,
                        company=self.company,
                        ytd_income=ytd_bruto_jan_nov,
                        ytd_tax_paid=ytd_tax_paid_jan_nov,
                    )
            else:
                # 6) Jalankan wrapper; jika partial-year -> TER bulanan, jika full-year -> annual
                res = calculate_pph21_desember(
                    employee=employee_doc,
                    company=self.company,
                    salary_slips=year_slips,
                    bruto_desember=bruto_desember,
                    pengurang_netto_desember=pengurang_netto_desember,
                    biaya_jabatan_desember=biaya_jabatan_desember,
                    partial_year_policy=policy,
                )
                # Jika wrapper memilih ANNUAL (full-year), pastikan koreksi pakai YTD APH yang akurat
                if res.get("pph21_annual", 0) and res.get("koreksi_pph21", 0) == res.get("pph21_annual", 0):
                    try:
                        res = calculate_pph21_december(
                            employee=employee_doc,
                            company=self.company,
                            ytd_bruto_jan_nov=ytd_bruto_jan_nov,
                            ytd_netto_jan_nov=ytd_netto_jan_nov,
                            ytd_tax_paid_jan_nov=ytd_tax_paid_jan_nov,
                            bruto_desember=bruto_desember,
                            pengurang_netto_desember=pengurang_netto_desember,
                            biaya_jabatan_desember=biaya_jabatan_desember,
                            jp_jht_employee_month=jp_jht_employee_month,
                        )
                    except TypeError:
                        res = calculate_pph21_december(
                            taxable_income=bruto_desember,
                            employee=employee_doc,
                            company=self.company,
                            ytd_income=ytd_bruto_jan_nov,
                            ytd_tax_paid=ytd_tax_paid_jan_nov,
                        )

            # 7) Posting ke slip
            tax_amount = flt(res.get("pph21_bulan", 0.0))
            self.tax = tax_amount
            try:
                self.tax_type = "DECEMBER"
            except AttributeError:
                res["_tax_type"] = "DECEMBER"

            self.pph21_info = json.dumps(res)
            self.update_pph21_row(tax_amount)

            frappe.logger().info(
                f"[DEC] {getattr(self, 'name', '')} policy={policy} bruto_des={bruto_desember} bj={biaya_jabatan_desember} "
                f"ytd_pph={ytd_tax_paid_jan_nov} -> tax_dec={tax_amount}"
            )
            return tax_amount

        except frappe.ValidationError:
            raise
        except Exception as e:
            frappe.log_error(
                message=f"Failed to calculate December income tax: {e}\n{traceback.format_exc()}",
                title=f"Payroll Indonesia December Calculation Error - {getattr(self, 'name', 'unknown')}",
            )
            raise frappe.ValidationError(f"Error in December PPh21 calculation: {e}")

    # -------------------------
    # Utilitas lain
    # -------------------------
    def _calculate_taxable_income(self):
        return {
            "earnings": getattr(self, "earnings", []),
            "deductions": getattr(self, "deductions", []),
            "start_date": getattr(self, "start_date", None),
            "name": getattr(self, "name", None),
        }

    def update_pph21_row(self, tax_amount: float):
        try:
            target = "PPh 21"
            found = False
            for d in self.deductions:
                sc = d.get("salary_component") if isinstance(d, dict) else getattr(d, "salary_component", None)
                if sc == target:
                    if isinstance(d, dict):
                        d["amount"] = tax_amount
                    else:
                        d.amount = tax_amount
                    found = True
                    break
            if not found:
                self.append("deductions", {"salary_component": target, "amount": tax_amount})
            self._recalculate_totals()
        except Exception as e:
            frappe.log_error(
                message=f"Failed to update PPh21 row for {self.name}: {e}\n{traceback.format_exc()}",
                title="Payroll Indonesia PPh21 Row Update Error",
            )
            raise frappe.ValidationError(f"Error updating PPh21 component: {e}")

    def _recalculate_totals(self):
        try:
            if hasattr(self, "set_totals") and callable(getattr(self, "set_totals")):
                self.set_totals()
            elif hasattr(self, "calculate_totals") and callable(getattr(self, "calculate_totals")):
                self.calculate_totals()
            elif hasattr(self, "calculate_net_pay") and callable(getattr(self, "calculate_net_pay")):
                self.calculate_net_pay()
            else:
                self._manual_totals_calculation()
            self._update_rounded_values()
        except Exception:
            # fallback manual
            self._manual_totals_calculation()
            self._update_rounded_values()

    def _manual_totals_calculation(self):
        def row_amount(row):
            return row.get("amount", 0) if isinstance(row, dict) else getattr(row, "amount", 0)

        def flag(row, name):
            return (row.get(name, 0) if isinstance(row, dict) else getattr(row, name, 0)) or 0

        def include(row):
            return not (flag(row, "do_not_include_in_total") or flag(row, "statistical_component"))

        self.gross_pay = sum(row_amount(r) for r in (self.earnings or []) if include(r))
        self.total_deduction = sum(row_amount(r) for r in (self.deductions or []) if include(r))
        self.net_pay = (self.gross_pay or 0) - (self.total_deduction or 0)
        if hasattr(self, "total"):
            self.total = self.net_pay
        self._update_rounded_values()

    def _update_rounded_values(self):
        try:
            if hasattr(self, "rounded_total") and hasattr(self, "total"):
                self.rounded_total = round(getattr(self, "total", self.net_pay))
            if hasattr(self, "rounded_net_pay"):
                self.rounded_net_pay = round(self.net_pay)
            if hasattr(self, "net_pay_in_words"):
                try:
                    from frappe.utils import money_in_words
                    self.net_pay_in_words = money_in_words(self.net_pay, getattr(self, "currency", "IDR"))
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Failed to update rounded values for {self.name}: {e}")

    # -------------------------
    # Hook validate & sync history
    # -------------------------
    def validate(self):
        try:
            try:
                super().validate()
            except frappe.ValidationError:
                raise
            except Exception as e:
                frappe.log_error(
                    message=f"Error in parent validate for Salary Slip {self.name}: {e}\n{traceback.format_exc()}",
                    title="Payroll Indonesia Validation Error",
                )

            if getattr(self, "tax_type", "") == "DECEMBER":
                tax_amount = self.calculate_income_tax_december()
            else:
                tax_amount = self.calculate_income_tax()

            self.update_pph21_row(tax_amount)
            logger.info(f"Validate: Updated PPh21 deduction row to {tax_amount}")

        except frappe.ValidationError:
            raise
        except Exception as e:
            frappe.log_error(
                message=f"Failed to update PPh21 in validate for Salary Slip {self.name}: {e}\n{traceback.format_exc()}",
                title="Payroll Indonesia PPh21 Update Error",
            )
            raise frappe.ValidationError(f"Error calculating PPh21: {e}")

    # -------------------------
    # Annual Payroll History sync
    # -------------------------
    def sync_to_annual_payroll_history(self, result, mode="monthly"):
        # Catatan: Bila Anda TIDAK ingin menulis APH sama sekali,
        # Anda bisa menonaktifkan pemanggilan fungsi ini di on_submit/on_cancel.
        if getattr(self, "_annual_history_synced", False):
            return

        try:
            if not getattr(self, "employee", None):
                logger.warning(f"No employee for Salary Slip {getattr(self, 'name', 'unknown')}, skip sync")
                return

            employee_doc = self.get_employee_doc() or {}
            employee_info = {
                "name": employee_doc.get("name") or self.employee,
                "company": employee_doc.get("company") or getattr(self, "company", None),
                "employee_name": employee_doc.get("employee_name"),
            }

            fiscal_year = getattr(self, "fiscal_year", None)
            if not fiscal_year and getattr(self, "start_date", None):
                fiscal_year = str(getdate(self.start_date).year)
            if not fiscal_year:
                logger.warning(f"Could not determine fiscal year for Salary Slip {self.name}, skipping sync")
                return

            nomor_bulan = self._get_bulan_number(
                start_date=getattr(self, "start_date", None),
                nama_bulan=getattr(self, "bulan", None),
            )

            raw_rate = result.get("rate", 0)
            numeric_rate = raw_rate if isinstance(raw_rate, (int, float)) else 0

            monthly_result = {
                "bulan": nomor_bulan,
                "bruto": result.get("bruto", result.get("bruto_total", 0)),
                "pengurang_netto": result.get("pengurang_netto", result.get("income_tax_deduction_total", 0)),
                "biaya_jabatan": result.get("biaya_jabatan", result.get("biaya_jabatan_total", 0)),
                "netto": result.get("netto", result.get("netto_total", 0)),
                "pkp": result.get("pkp", result.get("pkp_annual", 0)),
                "rate": flt(numeric_rate),
                "pph21": result.get("pph21", result.get("pph21_bulan", 0)),
                "salary_slip": self.name,
            }

            if mode == "monthly":
                sync_annual_payroll_history(
                    employee=employee_info, fiscal_year=fiscal_year, monthly_results=[monthly_result], summary=None
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
                if isinstance(raw_rate, str) and raw_rate:
                    summary["rate_slab"] = raw_rate
                sync_annual_payroll_history(
                    employee=employee_info, fiscal_year=fiscal_year, monthly_results=[monthly_result], summary=summary
                )

            self._annual_history_synced = True

        except frappe.ValidationError:
            raise
        except Exception as e:
            frappe.log_error(
                message=f"Failed to sync Annual Payroll History for {getattr(self, 'name', 'unknown')}: {e}\n{traceback.format_exc()}",
                title="Payroll Indonesia Annual History Sync Error",
            )
            logger.warning(f"Annual Payroll History sync failed for {self.name}: {e}")

    def on_submit(self):
        try:
            info = json.loads(getattr(self, "pph21_info", "{}") or "{}")
        except Exception:
            info = {}
        tax_type = getattr(self, "tax_type", None) or info.get("_tax_type")
        if not tax_type:
            bulan = self._get_bulan_number(start_date=getattr(self, "start_date", None))
            if bulan == 12:
                tax_type = "DECEMBER"
        mode = "december" if tax_type == "DECEMBER" else "monthly"
        self.sync_to_annual_payroll_history(info, mode=mode)
        if getattr(self, "_annual_history_synced", False):
            frappe.logger().info(f"[SYNC] Salary Slip {self.name} synced to Annual Payroll History")

    def on_cancel(self):
        if getattr(self, "flags", {}).get("from_annual_payroll_cancel"):
            return
        try:
            if not getattr(self, "employee", None):
                logger.warning(f"No employee for cancelled Salary Slip {getattr(self, 'name', 'unknown')}, skip")
                return

            fiscal_year = getattr(self, "fiscal_year", None) or str(getattr(self, "start_date", ""))[:4]
            if not fiscal_year:
                logger.warning(f"Could not determine fiscal year for cancelled Salary Slip {self.name}, skipping sync")
                return

            try:
                info = json.loads(getattr(self, "pph21_info", "{}") or "{}")
            except Exception:
                info = {}

            tax_type = getattr(self, "tax_type", None) or info.get("_tax_type")
            if not tax_type:
                bulan = self._get_bulan_number(start_date=getattr(self, "start_date", None))
                if bulan == 12:
                    tax_type = "DECEMBER"
            mode = "december" if tax_type == "DECEMBER" else "monthly"

            sync_annual_payroll_history(
                employee=self.employee,
                fiscal_year=fiscal_year,
                monthly_results=None,
                summary=None,
                cancelled_salary_slip=self.name,
                mode=mode,
            )
            frappe.logger().info(f"[SYNC] Salary Slip {self.name} removed from Annual Payroll History")
        except frappe.ValidationError:
            raise
        except Exception as e:
            frappe.log_error(
                message=f"Failed to remove from Annual Payroll History on cancel for {getattr(self, 'name', 'unknown')}: {e}\n{traceback.format_exc()}",
                title="Payroll Indonesia Annual History Cancel Error",
            )
            logger.warning(f"Failed to update Annual Payroll History when cancelling {self.name}: {e}")


def on_submit(doc, method=None):
    if isinstance(doc, CustomSalarySlip):
        return
    doc.__class__ = CustomSalarySlip
    doc.on_submit()


def on_cancel(doc, method=None):
    if isinstance(doc, CustomSalarySlip):
        return
    doc.__class__ = CustomSalarySlip
    doc.on_cancel()


def recalculate_slip_deductions(doc, method=None):
    """Recalculate salary slips when attendance changes, including fractional days."""
    try:
        slips = frappe.get_all(
            "Salary Slip",
            filters={
                "employee": doc.employee,
                "start_date": ["<=", doc.attendance_date],
                "end_date": [">=", doc.attendance_date],
                "docstatus": 1,
            },
            pluck="name",
        )
        for name in slips:
            slip = frappe.get_doc("Salary Slip", name)
            slip.deductions = [
                d
                for d in getattr(slip, "deductions", [])
                if (d.get("salary_component") if isinstance(d, dict) else getattr(d, "salary_component", None))
                != "Absence Deduction"
            ]
            if hasattr(slip, "_insert_absence_deduction"):
                slip._insert_absence_deduction()
            if hasattr(slip, "calculate_income_tax"):
                slip.calculate_income_tax()
            slip.save()
    except Exception:
        pass
