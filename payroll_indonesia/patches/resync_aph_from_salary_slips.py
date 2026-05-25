"""Bersihkan APH dummy & isi ulang dari Salary Slip yang sudah submit."""

import json

import frappe
from frappe.utils import flt, getdate

from payroll_indonesia.utils.sync_annual_payroll_history import (
	build_monthly_aph_row_from_salary_slip,
	get_aph_fiscal_year_from_salary_slip,
	recalculate_summary_from_monthly_details,
	sync_annual_payroll_history,
)


def execute():
	_clean_orphan_monthly_rows()
	_resync_submitted_slips()
	frappe.db.commit()


def _clean_orphan_monthly_rows():
	"""Hapus baris bulan 4 / bruto 0 dari fixture lama."""
	for child in frappe.get_all(
		"Annual Payroll History Child",
		fields=["name", "parent", "salary_slip", "bruto", "bulan"],
	):
		remove = False
		if not flt(child.bruto):
			slip = child.salary_slip
			if not slip or not frappe.db.exists("Salary Slip", slip):
				remove = True
			elif frappe.db.get_value("Salary Slip", slip, "docstatus") != 1:
				remove = True
		if remove:
			frappe.db.delete("Annual Payroll History Child", child.name)

	for aph_name in frappe.get_all("Annual Payroll History", pluck="name"):
		doc = frappe.get_doc("Annual Payroll History", aph_name)
		try:
			recalculate_summary_from_monthly_details(doc)
		except Exception:
			pass
		frappe.db.set_value(
			"Annual Payroll History",
			aph_name,
			{
				"bruto_total": doc.bruto_total,
				"netto_total": doc.netto_total,
				"pengurang_netto_total": getattr(doc, "pengurang_netto_total", 0),
				"biaya_jabatan_total": getattr(doc, "biaya_jabatan_total", 0),
				"pph21_annual": doc.pph21_annual,
			},
			update_modified=True,
		)


def _resync_submitted_slips():
	slip_fields = ["name", "employee", "start_date", "end_date", "gross_pay", "net_pay"]
	if frappe.get_meta("Salary Slip").has_field("tax"):
		slip_fields.append("tax")
	if frappe.get_meta("Salary Slip").has_field("pph21_info"):
		slip_fields.append("pph21_info")

	slips = frappe.get_all(
		"Salary Slip",
		filters={"docstatus": 1},
		fields=slip_fields,
		order_by="start_date asc",
	)
	for row in slips:
		doc = frappe.get_doc("Salary Slip", row.name)
		fiscal_year = get_aph_fiscal_year_from_salary_slip(doc)

		monthly_result = build_monthly_aph_row_from_salary_slip(doc)

		sync_annual_payroll_history(
			employee=doc.employee,
			fiscal_year=fiscal_year,
			monthly_results=[monthly_result],
			summary=None,
		)
