"""Runtime patch HRMS Salary Slip for Indonesia 25-24 cutoff periods.

HRMS normally looks up Salary Structure Assignment and fiscal year from
``start_date``. For a January payroll period like 25 Dec 2025 - 24 Jan 2026,
that makes HRMS search an SSA before 25 Dec 2025. In Indonesia payroll setup,
the salary month is January, so the lookup must use ``end_date``.
"""

from __future__ import annotations

import frappe
from frappe.utils import getdate


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

	self._salary_structure_assignment = frappe.db.get_value(
		"Salary Structure Assignment",
		{
			"employee": self.employee,
			"salary_structure": self.salary_structure,
			"from_date": ("<=", lookup_date),
			"docstatus": 1,
		},
		"*",
		order_by="from_date desc",
		as_dict=True,
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
