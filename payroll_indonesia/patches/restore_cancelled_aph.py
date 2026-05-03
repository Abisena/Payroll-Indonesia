import frappe

def execute():
    """Restore Annual Payroll History yang ter-cancel karena salary slip di-cancel."""
    cancelled_aph = frappe.get_all(
        "Annual Payroll History",
        filters={"docstatus": 2},
        fields=["name"]
    )
    for aph in cancelled_aph:
        frappe.db.set_value("Annual Payroll History", aph.name, "docstatus", 1)
        frappe.logger("payroll_indonesia").info(f"Restored APH {aph.name} from Cancelled to Submitted")
    
    frappe.db.commit()
    print(f"✅ Restored {len(cancelled_aph)} cancelled Annual Payroll History records")
