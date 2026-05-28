"""Ubah kolom bulan APH dari angka 1-12 menjadi nama bulan (Select)."""

import frappe

from payroll_indonesia.utils.aph_month import MONTH_INT_TO_LABEL, normalize_bulan


def execute():
	if not frappe.db.exists("DocType", "Annual Payroll History Child"):
		return

	_ensure_bulan_column_is_varchar()

	for row in frappe.db.sql(
		"""
		select name, bulan
		from `tabAnnual Payroll History Child`
		where bulan is not null and bulan != ''
		""",
		as_dict=True,
	):
		label = MONTH_INT_TO_LABEL.get(normalize_bulan(row.bulan))
		if label and row.bulan != label:
			frappe.db.set_value(
				"Annual Payroll History Child",
				row.name,
				"bulan",
				label,
				update_modified=False,
			)

	frappe.db.commit()
	frappe.clear_cache(doctype="Annual Payroll History Child")


def _ensure_bulan_column_is_varchar():
	column = frappe.db.sql(
		"""
		select data_type
		from information_schema.columns
		where table_schema = database()
			and table_name = 'tabAnnual Payroll History Child'
			and column_name = 'bulan'
		"""
	)
	if not column:
		return

	data_type = (column[0][0] or "").lower()
	if data_type in ("int", "bigint", "tinyint", "smallint", "mediumint"):
		frappe.db.sql(
			"""
			alter table `tabAnnual Payroll History Child`
			modify `bulan` varchar(140)
			"""
		)
