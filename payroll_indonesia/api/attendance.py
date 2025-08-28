import math

import frappe
from frappe import _
from frappe.utils import today


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in meters between two coordinates."""
    r = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


@frappe.whitelist()
def mobile_check_in(employee: str, latitude: float, longitude: float):
    """Validate employee proximity to office and create an attendance record."""
    settings = frappe.get_single("Payroll Indonesia Settings")
    if not (settings.office_latitude and settings.office_longitude):
        frappe.throw(_("Office coordinates are not set"))

    distance = _haversine(
        float(latitude),
        float(longitude),
        float(settings.office_latitude),
        float(settings.office_longitude),
    )
    if distance > 25:
        frappe.throw(_("Check-in location too far from office"), frappe.PermissionError)

    company = frappe.db.get_value("Employee", employee, "company")
    attendance = frappe.get_doc(
        {
            "doctype": "Attendance",
            "employee": employee,
            "company": company,
            "status": "Present",
            "attendance_date": today(),
        }
    )
    attendance.insert(ignore_permissions=True)
    return {"message": _("Attendance marked"), "name": attendance.name}
