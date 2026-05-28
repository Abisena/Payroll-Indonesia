/* payroll_indonesia APH form — v20260528 */
window.__payroll_indonesia_aph_form_js = true;

const APH_MONTH_NAMES = [
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
];

frappe.ui.form.on("Annual Payroll History", {
	refresh(frm) {
		enable_monthly_detail_editing(frm);
		calculate_totals(frm);
		add_summary_button(frm);

		if (!frm.is_new()) {
			frm.add_custom_button(__("Recalculate Totals"), () => {
				save_recalculated_totals(frm);
			});
		}
	},

	before_cancel(frm) {
		return new Promise((resolve, reject) => {
			frappe.confirm(
				__(
					"Urutan pembatalan:<br>" +
						"1. Batalkan semua Salary Slip terkait.<br>" +
						"2. Batalkan dokumen Annual Payroll History ini.<br><br>" +
						"Lanjutkan pembatalan?"
				),
				() => resolve(),
				() => reject()
			);
		});
	},
});

frappe.ui.form.on("Annual Payroll History Child", {
	bruto(frm, cdt, cdn) {
		auto_calculate_netto(frm, cdt, cdn);
		calculate_totals(frm);
	},
	pengurang_netto(frm, cdt, cdn) {
		auto_calculate_netto(frm, cdt, cdn);
		calculate_totals(frm);
	},
	biaya_jabatan(frm, cdt, cdn) {
		auto_calculate_netto(frm, cdt, cdn);
		calculate_totals(frm);
	},
	netto(frm) {
		calculate_totals(frm);
	},
	pkp(frm) {
		calculate_totals(frm);
	},
	pph21(frm) {
		calculate_totals(frm);
	},
	bulan(frm) {
		calculate_totals(frm);
	},
	monthly_details_add(frm, cdt, cdn) {
		const used = new Set(
			(frm.doc.monthly_details || [])
				.map((r) => bulan_to_int(r.bulan))
				.filter((m) => m >= 1 && m <= 12)
		);
		let next_month = 1;
		while (used.has(next_month) && next_month <= 12) {
			next_month += 1;
		}
		if (next_month <= 12) {
			frappe.model.set_value(cdt, cdn, "bulan", APH_MONTH_NAMES[next_month - 1]);
		}
		calculate_totals(frm);
	},
	monthly_details_remove(frm) {
		calculate_totals(frm);
		if (frm.doc.docstatus === 1) {
			save_recalculated_totals(frm, { quiet: true });
		}
	},
});

function bulan_to_int(value) {
	const as_int = cint(value);
	if (as_int >= 1 && as_int <= 12) {
		return as_int;
	}
	const text = String(value || "").trim().toLowerCase();
	const index = APH_MONTH_NAMES.findIndex((name) => name.toLowerCase() === text);
	return index >= 0 ? index + 1 : 0;
}

function enable_monthly_detail_editing(frm) {
	if (!frm.fields_dict.monthly_details) {
		return;
	}
	frm.set_df_property("monthly_details", "cannot_delete_rows", false);
	frm.set_df_property("monthly_details", "cannot_add_rows", frm.doc.docstatus === 2);
}

function auto_calculate_netto(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const bruto = flt(row.bruto || 0);
	const pengurang_netto = flt(row.pengurang_netto || 0);
	const biaya_jabatan = flt(row.biaya_jabatan || 0);
	const calculated_netto = bruto - pengurang_netto - biaya_jabatan;

	if (Math.abs(calculated_netto - flt(row.netto || 0)) > 0.1) {
		frappe.model.set_value(cdt, cdn, "netto", calculated_netto);
	}
}

function calculate_totals(frm) {
	const summary = get_monthly_summary(frm);
	let netto_total = summary.netto_total;

	if (Math.abs(summary.calculated_netto_total - netto_total) > 1) {
		netto_total = summary.calculated_netto_total;
	}

	const pph21_annual = flt(frm.doc.pph21_annual || 0);
	const koreksi_pph21 = pph21_annual - summary.pph21_jan_nov;

	frm.set_value("bruto_total", summary.bruto_total);
	frm.set_value("netto_total", netto_total);
	frm.set_value("pkp_annual", summary.pkp_annual);
	frm.set_value("koreksi_pph21", koreksi_pph21);

	if (frm.fields_dict.pengurang_netto_total) {
		frm.set_value("pengurang_netto_total", summary.pengurang_netto_total);
	}
	if (frm.fields_dict.biaya_jabatan_total) {
		frm.set_value("biaya_jabatan_total", summary.biaya_jabatan_total);
	}

	frm.refresh_fields([
		"bruto_total",
		"netto_total",
		"pkp_annual",
		"pph21_annual",
		"koreksi_pph21",
		"pengurang_netto_total",
		"biaya_jabatan_total",
	]);
}

function get_monthly_summary(frm) {
	const summary = {
		bruto_total: 0,
		pengurang_netto_total: 0,
		biaya_jabatan_total: 0,
		netto_total: 0,
		pkp_annual: 0,
		pph21_total: 0,
		pph21_jan_nov: 0,
		row_count: (frm.doc.monthly_details || []).length,
	};

	$.each(frm.doc.monthly_details || [], function (_i, row) {
		summary.bruto_total += flt(row.bruto || 0);
		summary.pengurang_netto_total += flt(row.pengurang_netto || 0);
		summary.biaya_jabatan_total += flt(row.biaya_jabatan || 0);
		summary.netto_total += flt(row.netto || 0);
		summary.pkp_annual += flt(row.pkp || 0);
		summary.pph21_total += flt(row.pph21 || 0);

		const bulan = bulan_to_int(row.bulan);
		if (bulan >= 1 && bulan <= 11) {
			summary.pph21_jan_nov += flt(row.pph21 || 0);
		}
	});

	summary.calculated_netto_total =
		summary.bruto_total - summary.pengurang_netto_total - summary.biaya_jabatan_total;

	return summary;
}

function format_currency_for_summary(frm, value) {
	const currency = frm.doc.currency || frappe.defaults.get_default("currency") || "IDR";
	return frappe.format(value || 0, { fieldtype: "Currency", options: currency }, null, frm.doc);
}

function add_summary_button(frm) {
	frm.add_custom_button(__("Lihat Ringkasan"), () => {
		show_summary_dialog(frm);
	});
}

function show_summary_dialog(frm) {
	const s = get_monthly_summary(frm);
	const rows = [
		[__("Jumlah Baris Bulan"), frappe.format(s.row_count || 0, { fieldtype: "Int" })],
		[__("Total Bruto"), format_currency_for_summary(frm, s.bruto_total)],
		[__("Total Pengurang"), format_currency_for_summary(frm, s.pengurang_netto_total)],
		[__("Total Biaya Jabatan"), format_currency_for_summary(frm, s.biaya_jabatan_total)],
		[__("Total Netto"), format_currency_for_summary(frm, s.netto_total)],
		[__("Netto Hasil Hitung"), format_currency_for_summary(frm, s.calculated_netto_total)],
		[__("Total PPh21"), format_currency_for_summary(frm, s.pph21_total)],
		[__("PPh21 Jan-Nov"), format_currency_for_summary(frm, s.pph21_jan_nov)],
	];

	const table_rows = rows
		.map(
			([label, value]) =>
				`<tr><td style="padding:6px 8px;">${frappe.utils.escape_html(label)}</td><td style="padding:6px 8px; text-align:right; white-space:nowrap;">${value}</td></tr>`
		)
		.join("");

	const d = new frappe.ui.Dialog({
		title: __("Ringkasan Jumlah Monthly Detail"),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "summary_html",
				options: `<div style="overflow:auto;"><table class="table table-bordered" style="margin-bottom:0;"><tbody>${table_rows}</tbody></table></div>`,
			},
		],
		primary_action_label: __("Tutup"),
		primary_action() {
			d.hide();
		},
	});

	d.show();
}

function save_recalculated_totals(frm, opts = {}) {
	const quiet = opts.quiet;
	frappe.call({
		method:
			"payroll_indonesia.payroll_indonesia.doctype.annual_payroll_history.annual_payroll_history.recalculate_and_save",
		args: { name: frm.doc.name },
		freeze: !quiet,
		freeze_message: quiet ? undefined : __("Menyimpan perhitungan ulang..."),
		callback(r) {
			if (!r.message) {
				return;
			}
			const t = r.message;
			frm.set_value("bruto_total", t.bruto_total);
			frm.set_value("netto_total", t.netto_total);
			frm.set_value("pph21_annual", t.pph21_annual);
			frm.set_value("koreksi_pph21", t.koreksi_pph21);
			frm.refresh_fields();
			if (!quiet) {
				frappe.show_alert({
					message: __("Total dan Koreksi PPh21 diperbarui."),
					indicator: "green",
				});
			}
		},
	});
}
