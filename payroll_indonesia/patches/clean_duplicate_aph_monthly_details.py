"""Hapus baris Monthly Detail duplikat / slip tidak ada di Annual Payroll History."""

import frappe
from frappe.utils import cint, flt

from payroll_indonesia.utils.sync_annual_payroll_history import (
	_remove_duplicate_monthly_rows,
	recalculate_summary_from_monthly_details,
)


def execute():
	for aph_name in frappe.get_all("Annual Payroll History", pluck="name"):
		child_names = frappe.get_all(
			"Annual Payroll History Child",
			filters={"parent": aph_name},
			fields=["name", "salary_slip", "bruto", "bulan"],
			order_by="modified asc",
		)
		if not child_names:
			continue

		delete_names = set()
		seen_slip = {}

		for row in child_names:
			slip = row.salary_slip
			if slip:
				if slip in seen_slip:
					delete_names.add(row.name)
					continue
				seen_slip[slip] = row.name

				if not frappe.db.exists("Salary Slip", slip):
					delete_names.add(row.name)
					continue
				if cint(frappe.db.get_value("Salary Slip", slip, "docstatus")) != 1 and not flt(
					row.bruto
				):
					delete_names.add(row.name)

		if not delete_names:
			continue

		for name in delete_names:
			frappe.db.delete("Annual Payroll History Child", name)

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
				"pkp_annual": doc.pkp_annual,
				"pph21_annual": doc.pph21_annual,
			},
			update_modified=True,
		)

	frappe.db.commit()
