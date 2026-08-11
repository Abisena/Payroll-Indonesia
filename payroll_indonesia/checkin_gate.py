"""Wajibkan karyawan (System User) mampir ke /checkin dulu sebelum masuk Desk,
selama dia belum absen (Employee Checkin log_type=IN) hari ini.

Ini bukan default Frappe/HRMS, dan gak nyala otomatis buat semua Employee.
Aktif per-orang lewat custom field "Wajib Absen Sebelum Masuk" (checkbox)
di form Employee, satu section sama field User ID -- default kosong/mati,
jadi harus dicentang manual per Employee.

Dipasang lewat hook `boot_session`: dijalankan setiap kali Desk (/app) dimuat,
jadi bukan cuma sekali pas login, tapi tiap kali dia buka/refresh Desk selama
belum absen hari itu.
"""

import frappe
from frappe.utils import now_datetime, today


def force_server_time(doc, method=None):
	"""before_insert Employee Checkin: cegah karyawan absen pakai jam palsu
	(jam device diubah, atau panggil API langsung) lewat halaman /checkin.

	Aturannya bukan berdasarkan role (role kayak "HR User" ternyata nempel
	juga ke akun karyawan biasa di sistem ini, jadi gak bisa dipercaya buat
	nentuin siapa yang "berhak"). Yang dipakai: SIAPA yang lagi diabsenin.
	- Ngabsenin diri sendiri (Employee.user_id == user yang lagi login)
	  -> jam server dipaksa, titik. Siapapun dia, HR sekalipun.
	- Nginput/ngoreksi jam punya ORANG LAIN (lewat Desk, misal lupa absen)
	  -> jam yang diinput dipercaya, karena itu jelas bukan self-checkin.
	"""
	employee_user = frappe.db.get_value("Employee", doc.employee, "user_id")
	if employee_user and employee_user == frappe.session.user:
		doc.time = now_datetime()


def boot_session(bootinfo):
	bootinfo.needs_checkin = False

	user = frappe.session.user
	if user in ("Administrator", "Guest"):
		return

	employee = frappe.db.get_value(
		"Employee",
		{"user_id": user, "status": "Active", "wajib_absen_sebelum_masuk": 1},
		"name",
	)
	if not employee:
		# bukan karyawan, belum ditautkan ke akun ini, atau toggle "Wajib Absen
		# Sebelum Masuk" di form Employee belum dicentang -> jangan di-gate
		return

	already_checked_in = frappe.db.exists(
		"Employee Checkin",
		{
			"employee": employee,
			"log_type": "IN",
			"time": [">=", f"{today()} 00:00:00"],
		},
	)

	bootinfo.needs_checkin = not bool(already_checked_in)
