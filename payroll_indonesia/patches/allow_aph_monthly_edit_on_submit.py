"""Izinkan edit/hapus baris Monthly Detail pada Annual Payroll History yang sudah submit."""

import frappe


def execute():
	# Parent: grid + tabel boleh diubah setelah submit
	for fieldname, prop, value, ptype in (
		("monthly_details", "allow_on_submit", "1", "Check"),
	):
		_make_or_update_property_setter("Annual Payroll History", fieldname, prop, value, ptype)

	if frappe.db.exists("DocType", "Annual Payroll History"):
		frappe.db.set_value(
			"DocType",
			"Annual Payroll History",
			"editable_grid",
			1,
			update_modified=False,
		)

	# Child rows: nilai boleh diedit setelah submit
	child_fields = [
		"bulan",
		"bruto",
		"pengurang_netto",
		"biaya_jabatan",
		"netto",
		"pkp",
		"rate",
		"pph21",
		"salary_slip",
	]
	for fieldname in child_fields:
		_make_or_update_property_setter(
			"Annual Payroll History Child", fieldname, "allow_on_submit", "1", "Check"
		)

	frappe.clear_cache(doctype="Annual Payroll History")


def _make_or_update_property_setter(doctype, fieldname, prop, value, ptype):
	ps_name = f"{doctype}-{fieldname}-{prop}"
	if frappe.db.exists("Property Setter", ps_name):
		frappe.db.set_value("Property Setter", ps_name, "value", value, update_modified=False)
		return
	frappe.make_property_setter(
		{
			"doctype": doctype,
			"doctype_or_field": "DocField",
			"fieldname": fieldname,
			"property": prop,
			"value": value,
			"property_type": ptype,
		},
		ignore_validate=True,
	)
