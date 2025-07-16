import sys
import types
import importlib.util


def test_payroll_entry_creates_salary_slips(monkeypatch):
    # stub frappe module
    frappe = types.ModuleType("frappe")
    frappe.db = types.SimpleNamespace(set_value=lambda *a, **k: None)
    frappe._ = lambda x: x
    frappe.utils = types.ModuleType("frappe.utils")
    frappe.utils.flt = float
    frappe.utils.cint = int
    frappe.utils.getdate = lambda *a, **k: None
    frappe.utils.add_days = lambda d, n=0: d
    frappe.utils.add_months = lambda d, m=0: d
    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = frappe.utils

    # minimal Document class
    model_module = types.ModuleType("frappe.model")
    document_module = types.ModuleType("frappe.model.document")

    class Document:
        def db_set(self, field, value):
            setattr(self, field, value)
        def submit(self):
            if hasattr(self, "before_submit"):
                self.before_submit()
            if hasattr(self, "on_submit"):
                self.on_submit()
            if hasattr(self, "after_submit"):
                self.after_submit()
            self.docstatus = 1

    document_module.Document = Document
    sys.modules["frappe.model"] = model_module
    sys.modules["frappe.model.document"] = document_module

    # store salary slip docs
    slip_store = {}
    def get_doc(doctype, name=None):
        if doctype == "Salary Slip":
            if name not in slip_store:
                slip = Document()
                slip.name = name
                slip.docstatus = 0
                slip_store[name] = slip
            return slip_store[name]
        raise KeyError(doctype)
    frappe.get_doc = get_doc

    # stub hrms payroll entry functions
    hrms_mod = types.ModuleType("hrms.payroll.doctype.payroll_entry.payroll_entry")
    def make_salary_slips(payroll_entry):
        return [f"SS-{i}" for i, _ in enumerate(payroll_entry.employees)]
    hrms_mod.make_salary_slips = make_salary_slips
    hrms_mod.enqueue_make_salary_slips = make_salary_slips
    sys.modules["hrms"] = types.ModuleType("hrms")
    sys.modules["hrms.payroll"] = types.ModuleType("hrms.payroll")
    sys.modules["hrms.payroll.doctype"] = types.ModuleType("hrms.payroll.doctype")
    sys.modules["hrms.payroll.doctype.payroll_entry"] = types.ModuleType("hrms.payroll.doctype.payroll_entry")
    sys.modules["hrms.payroll.doctype.payroll_entry.payroll_entry"] = hrms_mod

    # stub logger
    logger = types.SimpleNamespace(debug=lambda *a, **k: None, exception=lambda *a, **k: None)
    sys.modules["payroll_indonesia.frappe_helpers"] = types.SimpleNamespace(logger=logger)

    # import modules under test
    import importlib.util
    # load helper module to satisfy relative import
    func_spec = importlib.util.spec_from_file_location(
        "payroll_indonesia.override.payroll_entry_functions",
        "payroll_indonesia/override/payroll_entry_functions.py",
    )
    funcs = importlib.util.module_from_spec(func_spec)
    func_spec.loader.exec_module(funcs)
    sys.modules["payroll_indonesia.override.payroll_entry_functions"] = funcs

    spec = importlib.util.spec_from_file_location(
        "payroll_indonesia.override.payroll_entry",
        "payroll_indonesia/override/payroll_entry.py",
    )
    pe_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pe_module)

    global entry
    entry = pe_module.CustomPayrollEntry()
    entry.name = "PE-TEST"
    entry.employees = [object(), object()]

    entry.submit()

    assert slip_store["SS-0"].docstatus == 1
    assert slip_store["SS-1"].docstatus == 1
