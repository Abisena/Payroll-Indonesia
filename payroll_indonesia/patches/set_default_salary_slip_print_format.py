"""Jadikan Slip Gaji Modern sebagai default print Salary Slip."""

import frappe


DEFAULT_PRINT_FORMAT = "Slip Gaji Modern"


def execute():
	set_default_salary_slip_print_format()


def set_default_salary_slip_print_format():
	_set_doctype_property(
		"Salary Slip",
		"default_print_format",
		DEFAULT_PRINT_FORMAT,
		"Data",
	)
	frappe.clear_cache(doctype="Salary Slip")


def _set_doctype_property(doctype: str, prop: str, value: str, property_type: str):
	ps_name = frappe.db.get_value(
		"Property Setter",
		{
			"doc_type": doctype,
			"doctype_or_field": "DocType",
			"property": prop,
		},
	)
	if ps_name and frappe.db.exists("Property Setter", ps_name):
		frappe.db.set_value("Property Setter", ps_name, "value", value, update_modified=False)
		return

	frappe.make_property_setter(
		{
			"doctype": doctype,
			"doctype_or_field": "DocType",
			"property": prop,
			"value": value,
			"property_type": property_type,
		},
		ignore_validate=True,
		is_system_generated=0,
	)
