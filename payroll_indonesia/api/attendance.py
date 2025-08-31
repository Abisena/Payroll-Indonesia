import math
from enum import Enum

import frappe
try:
    from frappe.utils import today
except Exception:  # pragma: no cover - fallback when frappe.utils is unavailable
    from datetime import date

    def today() -> str:  # type: ignore
        return date.today().isoformat()

if not hasattr(frappe, "whitelist"):
    def whitelist(*_args, **_kwargs):  # type: ignore
        def decorator(fn):
            return fn

        return decorator

    frappe.whitelist = whitelist  # type: ignore


class AttendanceStatus(str, Enum):
    PRESENT = "Present"
    ABSENT = "Absent"
    HALF_DAY = "Half Day"
    ON_LEAVE = "On Leave"
    WORK_FROM_HOME = "Work From Home"
    HOLIDAY = "Holiday"


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
def mobile_check_in(
    employee: str, latitude: float, longitude: float, status: str | None = None
):
    """Validate employee proximity to office and create an attendance record."""
    settings = frappe.get_single("Payroll Indonesia Settings")

    coordinates = []
    if getattr(settings, "office_locations", None):
        coordinates = settings.office_locations
    elif settings.office_latitude and settings.office_longitude:
        coordinates = [frappe._dict(latitude=settings.office_latitude, longitude=settings.office_longitude)]
    else:
        frappe.throw(frappe._("Office coordinates are not set"))

    within_range = False
    for loc in coordinates:
        distance = _haversine(
            float(latitude),
            float(longitude),
            float(loc.latitude),
            float(loc.longitude),
        )
        if distance <= 10:
            within_range = True
            break

    if not within_range:
        frappe.throw(frappe._("Check-in location too far from office"), frappe.PermissionError)

    company = frappe.db.get_value("Employee", employee, "company")
    status_value = status or AttendanceStatus.PRESENT.value
    try:
        status_enum = AttendanceStatus(status_value)
    except ValueError:
        frappe.throw(_("Invalid status"))

    attendance = frappe.get_doc(
        {
            "doctype": "Attendance",
            "employee": employee,
            "company": company,
            "status": status_enum.value,
            "attendance_date": today(),
        }
    )
    attendance.insert(ignore_permissions=True)
    return {"message": frappe._("Attendance marked"), "name": attendance.name}
