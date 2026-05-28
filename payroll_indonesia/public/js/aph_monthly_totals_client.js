/* Client Script: baris Jumlah di Monthly Detail (Annual Payroll History) */
const APH_TOTAL_FIELDS = ["bruto", "pengurang_netto", "biaya_jabatan", "netto", "pph21"];

function aph_monthly_scope(frm) {
	return $(frm.wrapper).find('[data-fieldname="monthly_details"]');
}

function aph_sum_monthly(frm) {
	const totals = {};
	APH_TOTAL_FIELDS.forEach((f) => (totals[f] = 0));
	(frm.doc.monthly_details || []).forEach((row) => {
		APH_TOTAL_FIELDS.forEach((f) => {
			totals[f] += flt(row[f] || 0);
		});
	});
	return totals;
}

function aph_fmt_currency(value, frm) {
	const currency = frm.doc.currency || frappe.defaults.get_default("currency") || "IDR";
	const normalize = (text) => (text || "").replace("Rp ", "Rp\u00a0");
	if (typeof frappe.format_currency === "function") {
		return normalize(frappe.format_currency(value, currency));
	}
	const formatted = frappe.format(
		value,
		{ fieldtype: "Currency", options: currency },
		null,
		frm.doc
	);
	return normalize($("<div>").html(formatted).text().trim());
}

function aph_visible_columns(grid) {
	if (grid.visible_columns?.length) {
		return grid.visible_columns;
	}
	return (grid.docfields || [])
		.filter((df) => df.in_list_view && !df.hidden)
		.map((df) => [df, cint(df.columns) || 1]);
}

function aph_render_summary_button(frm) {
	const $scope = aph_monthly_scope(frm);
	const $buttons = $scope.find(".grid-buttons");
	if (!$buttons.length) {
		return;
	}

	$buttons.find(".aph-summary-btn").remove();
	const $btn = $(
		`<button type="button" class="btn btn-xs btn-secondary aph-summary-btn">${__("Lihat Ringkasan")}</button>`
	);
	$btn.on("click", () => aph_show_summary_dialog(frm));
	$buttons.append($btn);
}

function aph_show_summary_dialog(frm) {
	const totals = aph_sum_monthly(frm);
	const row_count = (frm.doc.monthly_details || []).length;
	const rows = [
		[__("Jumlah Baris"), frappe.format(row_count, { fieldtype: "Int" })],
		[__("Total Bruto"), aph_fmt_currency(totals.bruto, frm)],
		[__("Total Pengurang"), aph_fmt_currency(totals.pengurang_netto, frm)],
		[__("Total Biaya Jabatan"), aph_fmt_currency(totals.biaya_jabatan, frm)],
		[__("Total Netto"), aph_fmt_currency(totals.netto, frm)],
		[__("Total PPh21"), aph_fmt_currency(totals.pph21, frm)],
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

function aph_render_total_row(frm) {
	const $scope = aph_monthly_scope(frm);
	const grid = frm.fields_dict.monthly_details?.grid;
	if (!$scope.length || !grid || !(frm.doc.monthly_details || []).length) {
		return;
	}

	if (typeof grid.setup_visible_columns === "function") {
		grid.setup_visible_columns();
	}

	const visible_columns = aph_visible_columns(grid);
	if (!visible_columns.length) {
		return;
	}

	const totals = aph_sum_monthly(frm);
	const $rows = $scope.find(".grid-body .rows");
	if (!$rows.length) {
		return;
	}

	$scope.find(".aph-total-grid-row").remove();

	if (frm.fields_dict.monthly_details_jumlah) {
		frm.set_df_property("monthly_details_jumlah", "hidden", 1);
	}

	const $row = $('<div class="grid-row aph-total-grid-row"></div>');
	const $dataRow = $('<div class="data-row row aph-monthly-totals-row"></div>').appendTo($row);

	// Ikuti struktur baris default Frappe: checkbox + nomor urut + kolom data + aksi
	$('<div class="row-check col"></div>').appendTo($dataRow);
	$('<div class="row-index col"></div>').appendTo($dataRow);

	visible_columns.forEach(([df, colsize]) => {
		const $col = $(`<div class="col grid-static-col col-xs-${colsize}"></div>`)
			.attr("data-fieldname", df.fieldname)
			.attr("data-fieldtype", df.fieldtype || "")
			.appendTo($dataRow);

		const is_currency = APH_TOTAL_FIELDS.includes(df.fieldname);
		const $area = $(`<div class="static-area${is_currency ? " text-right" : ""}"></div>`).appendTo(
			$col
		);

		if (df.fieldname === "bulan") {
			// Hanya satu label: Jumlah (bukan "Jumlah" + "Total")
			$area.html(`<strong>${__("Jumlah")}</strong>`);
		} else if (is_currency) {
			$area.css({
				textAlign: "right",
				whiteSpace: "nowrap",
				overflow: "hidden",
				textOverflow: "ellipsis",
				display: "block",
				width: "100%",
			});
			$area.text(aph_fmt_currency(totals[df.fieldname], frm));
		}
	});

	// Kolom pensil kosong (supaya sejajar dengan baris di atas)
	$('<div class="col aph-total-action-col"></div>').appendTo($dataRow);
	$rows.append($row);

}

function aph_schedule_total_row(frm) {
	[150, 500, 1000].forEach((ms) => {
		setTimeout(() => {
			aph_render_total_row(frm);
			aph_render_summary_button(frm);
		}, ms);
	});
}

frappe.ui.form.on("Annual Payroll History", {
	refresh(frm) {
		aph_schedule_total_row(frm);
	},
});

frappe.ui.form.on("Annual Payroll History Child", {
	bruto(frm) {
		aph_schedule_total_row(frm);
	},
	pengurang_netto(frm) {
		aph_schedule_total_row(frm);
	},
	biaya_jabatan(frm) {
		aph_schedule_total_row(frm);
	},
	netto(frm) {
		aph_schedule_total_row(frm);
	},
	pph21(frm) {
		aph_schedule_total_row(frm);
	},
	monthly_details_remove(frm) {
		aph_schedule_total_row(frm);
	},
});
