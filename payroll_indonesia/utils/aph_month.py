"""Helper bulan untuk Annual Payroll History (grid pakai nama bulan)."""

from __future__ import annotations

from frappe.utils import cint

MONTH_LABELS = (
	"Januari",
	"Februari",
	"Maret",
	"April",
	"Mei",
	"Juni",
	"Juli",
	"Agustus",
	"September",
	"Oktober",
	"November",
	"Desember",
)

MONTH_LABEL_TO_INT = {label.lower(): index + 1 for index, label in enumerate(MONTH_LABELS)}
MONTH_INT_TO_LABEL = {index + 1: label for index, label in enumerate(MONTH_LABELS)}

MONTH_SELECT_OPTIONS = "\n".join(MONTH_LABELS)


def normalize_bulan(value) -> int:
	"""Terima angka 1-12 atau nama bulan, kembalikan nomor bulan (0 jika tidak valid)."""
	if value in (None, ""):
		return 0

	if isinstance(value, int) or (isinstance(value, str) and str(value).strip().isdigit()):
		month = cint(value)
		return month if 1 <= month <= 12 else 0

	text = str(value).strip().lower()
	return MONTH_LABEL_TO_INT.get(text, 0)


def bulan_to_label(value) -> str | None:
	month = normalize_bulan(value)
	return MONTH_INT_TO_LABEL.get(month) if month else None


def bulan_storage_value(value) -> str | None:
	"""Nilai yang disimpan di field Select child table."""
	return bulan_to_label(value)
