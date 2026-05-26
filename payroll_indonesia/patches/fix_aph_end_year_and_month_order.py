"""Pastikan APH mengikuti tahun akhir periode dan urutan bulan 1-12."""

import frappe
from frappe.utils import getdate

from payroll_indonesia.payroll_indonesia.doctype.annual_payroll_history.annual_payroll_history import (
	recalculate_aph_totals,
	sort_monthly_details,
)
from payroll_indonesia.utils.sync_annual_payroll_history import (
	build_monthly_aph_row_from_salary_slip,
	sync_annual_payroll_history,
)


def execute():
	moved = _move_cross_month_slips_to_end_year()
	sorted_docs = _sort_existing_aph_months()

	if moved or sorted_docs:
		frappe.db.commit()
		frappe.logger("payroll_indonesia").info(
			"fix_aph_end_year_and_month_order: moved %s slip(s), sorted %s APH doc(s)",
			moved,
			sorted_docs,
		)


def _move_cross_month_slips_to_end_year() -> int:
	moved = 0
	for row in frappe.get_all(
		"Salary Slip",
		filters={"docstatus": 1},
		fields=["name"],
	):
		doc = frappe.get_doc("Salary Slip", row.name)
		if not doc.start_date or not doc.end_date:
			continue

		start = getdate(doc.start_date)
		end = getdate(doc.end_date)
		if start.year == end.year and start.month == end.month:
			continue

		right_fy = str(end.year)
		wrong_years = {str(start.year)}
		if getattr(doc, "fiscal_year", None):
			wrong_years.add(str(doc.fiscal_year))
		wrong_years.discard(right_fy)

		for wrong_fy in wrong_years:
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
		moved += 1

	return moved


def _sort_existing_aph_months() -> int:
	sorted_docs = 0
	for row in frappe.get_all(
		"Annual Payroll History",
		filters={"docstatus": ["!=", 2]},
		fields=["name"],
	):
		doc = frappe.get_doc("Annual Payroll History", row.name)
		before = [r.name for r in (doc.get("monthly_details") or [])]
		sort_monthly_details(doc)
		after = [r.name for r in (doc.get("monthly_details") or [])]

		recalculate_aph_totals(doc)
		doc.flags.ignore_links = True
		doc.flags.ignore_permissions = True
		doc.flags.ignore_validate_update_after_submit = True
		doc.save()

		if before != after:
			sorted_docs += 1

	return sorted_docs
