# payroll_indonesia/override/employee.py
"""
Override Employee untuk handle perubahan has_bpjs:
- Draft salary slip otomatis di-recalculate
- Warning untuk submitted slip yang perlu di-amend manual
"""

import frappe
from frappe import _


def on_update(doc, method=None):
    """Trigger saat Employee di-save."""
    # Cek apakah has_bpjs berubah
    before = doc.get_doc_before_save()
    if not before:
        return

    before_bpjs = getattr(before, "has_bpjs", None)
    after_bpjs = getattr(doc, "has_bpjs", None)

    if before_bpjs == after_bpjs:
        return  # Tidak ada perubahan, skip

    _handle_bpjs_change(doc.name, doc.employee_name, after_bpjs)


def _handle_bpjs_change(employee, employee_name, has_bpjs):
    """Handle perubahan has_bpjs — update draft, warning submitted."""

    # 1) Cari semua draft salary slip employee ini
    draft_slips = frappe.get_all(
        "Salary Slip",
        filters={"employee": employee, "docstatus": 0},
        fields=["name"]
    )

    # 2) Recalculate semua draft slip
    updated = []
    for s in draft_slips:
        try:
            slip = frappe.get_doc("Salary Slip", s.name)
            slip.save(ignore_permissions=True, ignore_version=True)
            updated.append(s.name)
        except Exception as e:
            frappe.log_error(
                message=f"Failed to recalculate {s.name}: {e}",
                title="Payroll Indonesia BPJS Recalculate Error"
            )

    if updated:
        frappe.msgprint(
            _("Draft salary slip berikut telah di-recalculate: {0}").format(
                ", ".join(updated)
            ),
            alert=True,
            indicator="green"
        )

    # 3) Cari submitted slip yang perlu di-amend manual
    submitted_slips = frappe.get_all(
        "Salary Slip",
        filters={"employee": employee, "docstatus": 1},
        fields=["name", "start_date", "end_date"]
    )

    if submitted_slips:
        slip_list = "\n".join(
            [f"• {s.name} ({s.start_date} - {s.end_date})" for s in submitted_slips]
        )
        status = "dibebaskan dari" if has_bpjs else "dikenakan"
        frappe.msgprint(
            _(
                "Employee {0} sekarang <b>{1} BPJS</b>.<br><br>"
                "Salary slip berikut sudah <b>Submitted</b> dan perlu di-<b>Amend</b> manual "
                "agar perubahan BPJS berlaku:<br><pre>{2}</pre>"
            ).format(employee_name, status, slip_list),
            title=_("Perlu Amend Manual"),
            indicator="orange"
        )
