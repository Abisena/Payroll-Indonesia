"""Isi snapshot komponen gaji APH dari Salary Slip yang sudah ada."""

import frappe

from payroll_indonesia.utils.sync_annual_payroll_history import build_monthly_aph_row_from_salary_slip


def execute():
	frappe.reload_doc(
		"Payroll Indonesia",
		"doctype",
		"annual_payroll_history_child",
		force=True,
	)
	updated = 0
	for row in frappe.get_all(
		"Annual Payroll History",
		filters={"docstatus": ["!=", 2]},
		fields=["name"],
	):
		doc = frappe.get_doc("Annual Payroll History", row.name)
		changed = False
		for detail in doc.get("monthly_details") or []:
			if not detail.get("salary_slip") or not frappe.db.exists("Salary Slip", detail.salary_slip):
				continue

			snapshot = build_monthly_aph_row_from_salary_slip(detail.salary_slip)
			ssa_name = snapshot.get("salary_structure_assignment") or ""
			component_snapshot = snapshot.get("salary_component_snapshot") or ""

			if detail.get("salary_structure_assignment") != ssa_name:
				detail.salary_structure_assignment = ssa_name
				changed = True
			if detail.get("salary_component_snapshot") != component_snapshot:
				detail.salary_component_snapshot = component_snapshot
				changed = True

		if changed:
			doc.flags.ignore_links = True
			doc.flags.ignore_permissions = True
			doc.flags.ignore_validate_update_after_submit = True
			doc.save()
			updated += 1

	if updated:
		frappe.db.commit()
		frappe.logger("payroll_indonesia").info(
			"backfill_aph_salary_component_snapshot: updated %s APH document(s)",
			updated,
		)
