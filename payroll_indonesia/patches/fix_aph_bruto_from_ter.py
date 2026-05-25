"""Perbaiki bruto APH bulan 4+ yang tersimpan dari gross_pay (tanpa BPJS employer)."""

import frappe

from payroll_indonesia.utils.sync_annual_payroll_history import (
	build_monthly_aph_row_from_salary_slip,
	recalculate_summary_from_monthly_details,
	sync_annual_payroll_history,
)


def execute():
	slips = frappe.get_all(
		"Salary Slip",
		filters={"docstatus": 1},
		pluck="name",
		order_by="start_date asc",
	)
	for name in slips:
		doc = frappe.get_doc("Salary Slip", name)
		fiscal_year = getattr(doc, "fiscal_year", None)
		if not fiscal_year and doc.start_date:
			from frappe.utils import getdate

			fiscal_year = str(getdate(doc.start_date).year)
		if not fiscal_year:
			continue

		row = build_monthly_aph_row_from_salary_slip(doc)
		sync_annual_payroll_history(
			employee=doc.employee,
			fiscal_year=fiscal_year,
			monthly_results=[row],
			summary=None,
		)

	for aph_name in frappe.get_all("Annual Payroll History", pluck="name"):
		doc = frappe.get_doc("Annual Payroll History", aph_name)
		recalculate_summary_from_monthly_details(doc)
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

	frappe.db.commit()
