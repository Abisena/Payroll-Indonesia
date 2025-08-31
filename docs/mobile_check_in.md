# Mobile Check-In API

Endpoint: `/api/method/payroll_indonesia.api.attendance.mobile_check_in`

## Parameters

| Name       | Type  | Description               |
|------------|-------|---------------------------|
| `employee` | Data  | ID of the employee        |
| `latitude` | Float | Current latitude in WGS84 |
| `longitude`| Float | Current longitude in WGS84|
| `status`   | Data  | Optional attendance status. Defaults to `Present`. |

Valid values: `Present`, `Absent`, `Half Day`, `On Leave`, `Work From Home`, `Holiday`.

## Example Request

```bash
curl -X POST https://example.com/api/method/payroll_indonesia.api.attendance.mobile_check_in \
  -d "employee=EMP-0001" \
  -d "latitude=-6.1754" \
  -d "longitude=106.8272" \
  -d "status=Work From Home"
```

### Success `200`

```json
{"message": "Attendance marked", "name": "ATT-0001"}
```

### Out of Range `403`

```json
{"exc": "frappe.PermissionError: Check-in location too far from office"}
```
