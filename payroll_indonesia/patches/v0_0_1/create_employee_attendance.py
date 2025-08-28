import frappe


def execute():
    """Create Employee Attendance doctype."""
    frappe.reload_doc("payroll_indonesia", "doctype", "employee_attendance")
