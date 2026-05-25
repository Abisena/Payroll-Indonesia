"""Pindahkan baris APH bulan gaji Jan dari FY salah (start_date) ke FY end_date (cutoff 25–24)."""

import frappe
from frappe.utils import getdate

from payroll_indonesia.utils.sync_annual_payroll_history import (
	build_monthly_aph_row_from_salary_slip,
	get_aph_fiscal_year_from_salary_slip,
	sync_annual_payroll_history,
)


def execute():
	slips = frappe.get_all(
		"Salary Slip",
		filters={"docstatus": 1},
		fields=["name"],
	)
	fixed = 0
	for row in slips:
		doc = frappe.get_doc("Salary Slip", row.name)
		if not doc.start_date or not doc.end_date:
			continue
		start = getdate(doc.start_date)
		end = getdate(doc.end_date)
		if start.year == end.year and start.month == end.month:
			continue

		wrong_fy = str(start.year)
		right_fy = get_aph_fiscal_year_from_salary_slip(doc)
		if wrong_fy == right_fy:
			continue

		sync_annual_payroll_history(
			employee=doc.employee,
			fiscal_year=wrong_fy,
			cancelled_salary_slip=doc.name,
		)
		sync_annual_payroll_history(
			employee=doc.employee,
			fiscal_year=right_fy,
			monthly_results=[build_monthly_aph_row_from_salary_slip(doc)],
		)
		fixed += 1

	if fixed:
		frappe.db.commit()
		frappe.logger("payroll_indonesia").info(
			"fix_aph_cutoff_fiscal_year: moved %s cross-month slip(s) to correct APH year",
			fixed,
		)
