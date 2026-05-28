"""Runtime patch HRMS Salary Slip for Indonesia 25-24 cutoff periods.

HRMS normally looks up Salary Structure Assignment and fiscal year from
``start_date``. For a January payroll period like 25 Dec 2025 - 24 Jan 2026,
that makes HRMS search an SSA before 25 Dec 2025. In Indonesia payroll setup,
the salary month is January, so the lookup must use ``end_date``.
"""

from __future__ import annotations

import frappe
from frappe.utils import getdate


def _replacement_assignment_applies(replacement_name, lookup_date) -> bool:
	if not replacement_name or not frappe.db.exists("Salary Structure Assignment", replacement_name):
		return False
	replacement = frappe.db.get_value(
		"Salary Structure Assignment",
		replacement_name,
		["from_date", "end_date", "docstatus"],
		as_dict=True,
	)
	if not replacement or replacement.get("docstatus") != 1:
		return False
	if replacement.get("from_date") and getdate(replacement.from_date) > getdate(lookup_date):
		return False
	if replacement.get("end_date") and getdate(replacement.end_date) < getdate(lookup_date):
		return False
	return True


def _is_cutoff_cross_month_period(self) -> bool:
	if not (getattr(self, "start_date", None) and getattr(self, "end_date", None)):
		return False
	start = getdate(self.start_date)
	end = getdate(self.end_date)
	return start.month != end.month or start.year != end.year


def _salary_month_reference_date(self):
	if _is_cutoff_cross_month_period(self):
		return getdate(self.end_date)
	return getdate(getattr(self, "actual_start_date", None) or self.start_date)


def set_salary_structure_assignment(self):
	from frappe import _
	from frappe.utils.formatters import formatdate

	lookup_date = _salary_month_reference_date(self)

	assignment_rows = frappe.get_all(
		"Salary Structure Assignment",
		filters={
			"employee": self.employee,
			"salary_structure": self.salary_structure,
			"from_date": ("<=", lookup_date),
			"docstatus": 1,
		},
		fields=["*"],
		order_by="from_date desc, creation desc",
	)
	candidate = None
	for row in assignment_rows:
		if row.get("renewed_by_assignment_contract") and _replacement_assignment_applies(
			row.get("renewed_by_assignment_contract"), lookup_date
		):
			continue
		if row.get("end_date") and getdate(row.end_date) < lookup_date:
			continue
		candidate = row
		break
	self._salary_structure_assignment = (
		candidate
		if candidate
		else None
	)

	if not self._salary_structure_assignment:
		frappe.throw(
			_(
				"Please assign a Salary Structure for Employee {0} applicable from or before {1} first"
			).format(
				frappe.bold(self.employee_name),
				frappe.bold(formatdate(lookup_date)),
			)
		)

	if self._salary_structure_assignment.get("name"):
		self.salary_structure_assignment = self._salary_structure_assignment.name


def get_year_to_date_period(self):
	if getattr(self, "payroll_period", None):
		return self.payroll_period.start_date, self.payroll_period.end_date

	from erpnext.accounts.utils import get_fiscal_year

	lookup_date = _salary_month_reference_date(self)
	fiscal_year = get_fiscal_year(date=lookup_date, company=self.company, as_dict=1)
	return fiscal_year.year_start_date, fiscal_year.year_end_date


def apply_salary_slip_cutoff_patch() -> None:
	"""Patch the base HRMS class too, for sites where method resolution hits HRMS."""
	try:
		from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip
	except Exception:
		return

	SalarySlip._is_cutoff_cross_month_period = _is_cutoff_cross_month_period
	SalarySlip._salary_month_reference_date = _salary_month_reference_date
	SalarySlip.set_salary_structure_assignment = set_salary_structure_assignment
	SalarySlip.get_year_to_date_period = get_year_to_date_period
