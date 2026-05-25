import json
import re

import frappe
from frappe.utils import cint, flt, getdate
from frappe.model.document import Document


def recalculate_aph_totals(doc) -> dict:
	"""
	Hitung ulang ringkasan dari monthly_details.
	koreksi_pph21 = pph21_annual - total PPh21 bulan 1–11 (bukan total semua bulan).
	"""
	bruto_total = pengurang_netto_total = biaya_jabatan_total = 0.0
	netto_total = pkp_annual = 0.0
	pph21_jan_nov = 0.0

	for row in doc.get("monthly_details") or []:
		bruto = flt(row.bruto)
		pengurang_netto = flt(getattr(row, "pengurang_netto", 0))
		biaya_jabatan = flt(getattr(row, "biaya_jabatan", 0))
		bulan = cint(row.bulan)

		calculated_netto = bruto - pengurang_netto - biaya_jabatan
		stored_netto = flt(row.netto)
		if abs(calculated_netto - stored_netto) > 0.1:
			row.netto = calculated_netto
			stored_netto = calculated_netto

		bruto_total += bruto
		netto_total += stored_netto
		pkp_annual += flt(row.pkp)
		pengurang_netto_total += pengurang_netto
		biaya_jabatan_total += biaya_jabatan

		if 1 <= bulan <= 11:
			pph21_jan_nov += flt(row.pph21)

	doc.bruto_total = bruto_total
	doc.pengurang_netto_total = pengurang_netto_total
	doc.biaya_jabatan_total = biaya_jabatan_total
	doc.netto_total = bruto_total - pengurang_netto_total - biaya_jabatan_total
	doc.pkp_annual = pkp_annual
	doc.ptkp_annual = flt(doc.ptkp_annual) or 0

	pph21_annual = flt(doc.pph21_annual)
	if not pph21_annual:
		# Fallback: jumlah PPh semua baris (data lama tanpa field tahunan terpisah)
		pph21_annual = sum(flt(r.pph21) for r in (doc.get("monthly_details") or []))
		doc.pph21_annual = pph21_annual

	doc.koreksi_pph21 = pph21_annual - pph21_jan_nov

	return {
		"bruto_total": doc.bruto_total,
		"netto_total": doc.netto_total,
		"pph21_annual": doc.pph21_annual,
		"pph21_jan_nov": pph21_jan_nov,
		"koreksi_pph21": doc.koreksi_pph21,
	}


class AnnualPayrollHistory(Document):
	def validate(self):
		recalculate_aph_totals(self)

	def on_cancel(self):
		"""Cancel linked Salary Slips when this document is cancelled."""
		logger = frappe.logger("payroll_indonesia")

		if getattr(self, "skip_salary_slip_cancellation", False):
			logger.info(f"Skipping salary slip cancellation for {self.name} due to flag")
			return

		slips = [
			row.salary_slip
			for row in (self.monthly_details or [])
			if getattr(row, "salary_slip", None)
		]

		if not slips:
			logger.info(f"No salary slips found for {self.name}")
			return

		slip_docs = []
		for slip_name in slips:
			try:
				slip_doc = frappe.get_doc("Salary Slip", slip_name)
				slip_docs.append(slip_doc)
				logger.info(f"Queued Salary Slip {slip_name} for cancellation")
			except Exception as e:
				logger.error(f"Unable to retrieve Salary Slip {slip_name}: {e}")

		december_slips, other_slips = [], []
		for slip_doc in slip_docs:
			posting_date = getattr(slip_doc, "posting_date", None)
			start_date = getattr(slip_doc, "start_date", None)
			month_source = posting_date or start_date
			month = getdate(month_source).month if month_source else None

			tax_type = getattr(slip_doc, "tax_type", None)
			if not tax_type:
				info_json = getattr(slip_doc, "pph21_info", None)
				if info_json:
					try:
						info = json.loads(info_json)
						tax_type = info.get("_tax_type")
					except Exception as e:
						logger.error(f"Error parsing pph21_info for {slip_doc.name}: {e}")

			if tax_type == "DECEMBER" or month == 12:
				december_slips.append(slip_doc)
			else:
				other_slips.append(slip_doc)

		december_slips.sort(
			key=lambda d: getattr(d, "posting_date", None) or getattr(d, "start_date", None),
			reverse=True,
		)
		other_slips.sort(
			key=lambda d: getattr(d, "posting_date", None) or getattr(d, "start_date", None),
			reverse=True,
		)
		slip_docs = december_slips + other_slips

		cancelled, failed = [], []
		for slip in slip_docs:
			savepoint = re.sub(r"\W+", "_", f"cancel_{slip.name}")[:63]
			try:
				frappe.db.savepoint(savepoint)
				logger.info(f"Cancelling Salary Slip {slip.name}")
				slip.flags.from_annual_payroll_cancel = True
				slip.cancel()
				frappe.db.commit()
				cancelled.append(slip.name)
				logger.info(f"Cancelled Salary Slip {slip.name}")
			except Exception as e:
				frappe.db.rollback(save_point=savepoint)
				failed.append(slip.name)
				logger.error(f"Failed to cancel Salary Slip {slip.name}: {e}")

		summary = []
		if cancelled:
			summary.append(f"Berhasil dibatalkan: {len(cancelled)} slip")
		if failed:
			summary.append(f"Gagal dibatalkan: {len(failed)} slip")

		message = "<br>".join(summary) if summary else "Tidak ada salary slip yang dibatalkan."
		frappe.msgprint(message, title="Ringkasan Pembatalan Salary Slip")
		logger.info(f"Cancellation summary for {self.name}: {message}")


@frappe.whitelist()
def recalculate_and_save(name: str) -> dict:
	"""Hitung ulang total & koreksi lalu simpan (submitted doc dengan allow_on_submit)."""
	doc = frappe.get_doc("Annual Payroll History", name)
	if not doc.has_permission("write"):
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

	totals = recalculate_aph_totals(doc)
	doc.save(ignore_permissions=True)
	return totals
