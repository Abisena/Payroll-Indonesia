frappe.ui.form.on("Annual Payroll History", {
	refresh(frm) {
		enable_monthly_detail_editing(frm);
		calculate_totals(frm);

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
				.map((r) => cint(r.bulan))
				.filter((m) => m >= 1 && m <= 12)
		);
		let next_month = 1;
		while (used.has(next_month) && next_month <= 12) {
			next_month += 1;
		}
		if (next_month <= 12) {
			frappe.model.set_value(cdt, cdn, "bulan", next_month);
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

function enable_monthly_detail_editing(frm) {
	if (!frm.fields_dict.monthly_details) {
		return;
	}
	// Submitted: tetap bisa pilih & hapus baris (tanpa cancel dokumen)
	frm.set_df_property("monthly_details", "cannot_delete_rows", false);
	frm.set_df_property("monthly_details", "cannot_add_rows", frm.doc.docstatus === 2);
	frm.refresh_field("monthly_details");
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
	let bruto_total = 0;
	let netto_total = 0;
	let pkp_annual = 0;
	let pengurang_netto_total = 0;
	let biaya_jabatan_total = 0;
	let pph21_jan_nov = 0;

	$.each(frm.doc.monthly_details || [], function (_i, row) {
		bruto_total += flt(row.bruto || 0);
		netto_total += flt(row.netto || 0);
		pkp_annual += flt(row.pkp || 0);
		pengurang_netto_total += flt(row.pengurang_netto || 0);
		biaya_jabatan_total += flt(row.biaya_jabatan || 0);

		const bulan = cint(row.bulan);
		if (bulan >= 1 && bulan <= 11) {
			pph21_jan_nov += flt(row.pph21 || 0);
		}
	});

	const calculated_netto_total =
		bruto_total - pengurang_netto_total - biaya_jabatan_total;

	if (Math.abs(calculated_netto_total - netto_total) > 1) {
		netto_total = calculated_netto_total;
	}

	let pph21_annual = flt(frm.doc.pph21_annual || 0);
	const koreksi_pph21 = pph21_annual - pph21_jan_nov;

	frm.set_value("bruto_total", bruto_total);
	frm.set_value("netto_total", netto_total);
	frm.set_value("pkp_annual", pkp_annual);
	frm.set_value("koreksi_pph21", koreksi_pph21);

	if (frm.fields_dict.pengurang_netto_total) {
		frm.set_value("pengurang_netto_total", pengurang_netto_total);
	}
	if (frm.fields_dict.biaya_jabatan_total) {
		frm.set_value("biaya_jabatan_total", biaya_jabatan_total);
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
