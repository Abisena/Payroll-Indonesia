// Paksa ke halaman /checkin selama karyawan belum absen (IN) hari ini.
// frappe.boot sudah tersedia di titik ini (disisipkan server sebelum script ini di-load).
(function () {
	if (frappe.boot && frappe.boot.needs_checkin && !window.location.pathname.startsWith("/checkin")) {
		window.location.href = "/checkin";
	}
})();
