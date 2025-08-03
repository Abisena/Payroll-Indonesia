function set_indonesia_flags(frm) {
    const date = frm.doc.posting_date || frm.doc.start_date;
    if (!date) {
        frm.set_value('run_payroll_indonesia', 0);
        frm.set_value('run_payroll_indonesia_december', 0);
        return;
    }
    const month = frappe.datetime.str_to_obj(date).getMonth() + 1;
    if (month === 12) {
        frm.set_value('run_payroll_indonesia', 0);
        frm.set_value('run_payroll_indonesia_december', 1);
    } else {
        frm.set_value('run_payroll_indonesia', 1);
        frm.set_value('run_payroll_indonesia_december', 0);
    }
}

frappe.ui.form.on('Payroll Entry', {
    onload: function(frm) {
        set_indonesia_flags(frm);
    },
    posting_date: function(frm) {
        set_indonesia_flags(frm);
    },
    start_date: function(frm) {
        set_indonesia_flags(frm);
    }
});
