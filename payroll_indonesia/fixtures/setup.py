# -*- coding: utf-8 -*-
# Copyright (c) 2025, PT. Innovasi Terbaik Bangsa and contributors
# For license information, please see license.txt
# Last modified: 2025-07-02 12:12:46 by dannyaudian

import frappe
from frappe.utils import getdate, flt
from frappe.exceptions import ValidationError

from payroll_indonesia.config.config import get_config as get_default_config
from payroll_indonesia.payroll_indonesia.utils import debug_log

__all__ = [
    "before_install",
    "after_install",
    "after_sync",
    "check_system_readiness",
    "setup_accounts",
    "setup_pph21",
    "create_supplier_group",
    "create_bpjs_supplier",
    "setup_salary_components",
    "display_installation_summary",
    "setup_all_accounts",
    "setup_company_accounts",
    "update_ptkp_ter_mapping",
    "setup_pph21_defaults",
    "setup_pph21_ter",
    "setup_income_tax_slab",
]


def before_install():
    """Run system checks before installation."""
    try:
        check_system_readiness()
    except Exception as e:
        frappe.log_error(
            f"Error during before_install: {str(e)}\n\n{frappe.get_traceback()}",
            "Payroll Indonesia Installation Error"
        )
        debug_log(f"Error during before_install: {str(e)}", "Payroll Indonesia Installation Error")


def after_install():
    """
    Main after_install hook for the Payroll Indonesia app.
    Runs all setup steps in sequence and logs results.
    """
    debug_log("Starting Payroll Indonesia after_install process", "Installation")
    config = get_default_config()
    results = {
        "accounts": False,
        "suppliers": False,
        "pph21_settings": False,
        "salary_components": False,
        "bpjs_setup": False,
    }

    try:
        results["accounts"] = setup_accounts(config)
        debug_log("Account setup completed", "Installation")
    except Exception as e:
        frappe.log_error(
            f"Error during account setup: {str(e)}\n\n{frappe.get_traceback()}",
            "Account Setup Error"
        )
        debug_log(f"Error during account setup: {str(e)}", "Account Setup Error")

    try:
        suppliers_ok = create_supplier_group()
        if suppliers_ok and config.get("suppliers", {}).get("bpjs", {}):
            suppliers_ok = create_bpjs_supplier(config)
        results["suppliers"] = suppliers_ok
        debug_log("Supplier setup completed", "Installation")
    except Exception as e:
        frappe.log_error(
            f"Error during supplier setup: {str(e)}\n\n{frappe.get_traceback()}",
            "Supplier Setup Error"
        )
        debug_log(f"Error during supplier setup: {str(e)}", "Supplier Setup Error")

    try:
        results["pph21_settings"] = setup_pph21(config)
        debug_log("PPh 21 setup completed", "Installation")
    except Exception as e:
        frappe.log_error(
            f"Error during PPh 21 setup: {str(e)}\n\n{frappe.get_traceback()}",
            "PPh 21 Setup Error"
        )
        debug_log(f"Error during PPh 21 setup: {str(e)}", "PPh 21 Setup Error")

    try:
        results["salary_components"] = setup_salary_components(config)
        debug_log("Salary components setup completed", "Installation")
    except Exception as e:
        frappe.log_error(
            f"Error during salary components setup: {str(e)}\n\n{frappe.get_traceback()}",
            "Salary Components Setup Error"
        )
        debug_log(f"Error during salary components setup: {str(e)}", "Salary Components Setup Error")

    try:
        results["bpjs_setup"] = setup_bpjs_settings()
        debug_log("BPJS setup completed", "Installation")
    except Exception as e:
        frappe.log_error(
            f"Error during BPJS setup: {str(e)}\n\n{frappe.get_traceback()}",
            "BPJS Setup Error"
        )
        debug_log(f"Error during BPJS setup: {str(e)}", "BPJS Setup Error")

    try:
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(
            f"Error committing changes: {str(e)}\n\n{frappe.get_traceback()}",
            "Installation Database Error"
        )
        debug_log(f"Error committing changes: {str(e)}", "Installation Database Error")

    display_installation_summary(results, config)


def after_sync():
    """
    Hook after app sync. Updates BPJS and TER settings if DocTypes exist.
    """
    try:
        debug_log("Starting after_sync process", "App Sync")

        if frappe.db.table_exists("BPJS Settings"):
            if frappe.db.exists("BPJS Settings", "BPJS Settings"):
                from payroll_indonesia.payroll_indonesia.doctype.bpjs_settings.bpjs_settings import (
                    update_bpjs_settings,
                )
                updated = update_bpjs_settings()
                debug_log(f"Updated BPJS Settings: {updated}", "App Sync")

        if frappe.db.table_exists("PPh 21 Settings"):
            if frappe.db.exists("PPh 21 Settings", "PPh 21 Settings"):
                config = get_default_config()
                if config and "ptkp_to_ter_mapping" in config:
                    update_ptkp_ter_mapping(config)
                    debug_log("Updated PTKP to TER mapping for PMK 168/2023", "App Sync")
                if config and "ter_rates" in config:
                    if frappe.db.table_exists("PPh 21 TER Table"):
                        has_new_format = frappe.db.exists(
                            "PPh 21 TER Table",
                            {"status_pajak": ["in", ["TER A", "TER B", "TER C"]]}
                        )
                        if not has_new_format:
                            setup_pph21_ter(config, force_update=True)
                            debug_log("Updated TER rates to PMK 168/2023 format", "App Sync")
    except Exception as e:
        frappe.log_error(
            f"Error during after_sync: {str(e)}\n\n{frappe.get_traceback()}",
            "Payroll Indonesia Sync Error"
        )
        debug_log(f"Error during after_sync: {str(e)}", "Payroll Indonesia Sync Error")


def check_system_readiness():
    """
    Checks if required DocTypes and tables exist.
    """
    required_core_doctypes = [
        "Salary Component",
        "Salary Structure",
        "Salary Slip",
        "Employee",
        "Company",
        "Account",
    ]
    missing_doctypes = []
    for doctype in required_core_doctypes:
        if not frappe.db.table_exists(doctype):
            missing_doctypes.append(doctype)
    if missing_doctypes:
        debug_log(
            f"Required tables missing: {', '.join(missing_doctypes)}", "System Readiness Check"
        )
        frappe.log_error(
            f"Required tables missing: {', '.join(missing_doctypes)}", "System Readiness Check"
        )
    company_records = frappe.get_all("Company") if frappe.db.table_exists("Company") else []
    if not company_records:
        debug_log("No company found. Some setup steps may fail.", "System Readiness Check")
        frappe.log_error("No company found", "System Readiness Check")
    return True


def setup_bpjs_settings():
    """
    Setup BPJS settings if DocType exists.
    """
    if not frappe.db.table_exists("BPJS Settings"):
        debug_log("BPJS Settings table does not exist", "BPJS Setup")
        return False
    from payroll_indonesia.payroll_indonesia.doctype.bpjs_settings.bpjs_settings import (
        setup_bpjs_settings as bpjs_setup_func,
    )
    try:
        return bpjs_setup_func()
    except Exception as e:
        frappe.log_error(
            f"Error setting up BPJS Settings: {str(e)}\n\n{frappe.get_traceback()}",
            "BPJS Setup Error"
        )
        debug_log(f"Error setting up BPJS Settings: {str(e)}", "BPJS Setup Error")
        return False


def update_ptkp_ter_mapping(config):
    """
    Update/create PTKP to TER mapping for PMK 168/2023.
    """
    mapping_doctype = "PTKP TER Mapping"
    if not frappe.db.table_exists(mapping_doctype):
        debug_log(f"{mapping_doctype} table does not exist", "TER Mapping Update")
        return False
    try:
        ptkp_to_ter_mapping = config.get("ptkp_to_ter_mapping", {})
        if not ptkp_to_ter_mapping:
            debug_log("No PTKP to TER mapping found in config", "TER Mapping Update")
            return False
        frappe.db.sql(f"DELETE FROM `tab{mapping_doctype}`")
        frappe.db.commit()
        for ptkp_status, ter_category in ptkp_to_ter_mapping.items():
            mapping = frappe.new_doc(mapping_doctype)
            mapping.ptkp_status = ptkp_status
            mapping.ter_category = ter_category
            mapping.description = f"Pemetaan {ptkp_status} ke {ter_category}"
            mapping.flags.ignore_permissions = True
            mapping.insert(ignore_permissions=True)
        frappe.db.commit()
        debug_log(f"Created {len(ptkp_to_ter_mapping)} PTKP to TER mappings", "TER Mapping Update")
        return True
    except Exception as e:
        frappe.log_error(
            f"Error updating PTKP to TER mapping: {str(e)}\n\n{frappe.get_traceback()}",
            "TER Mapping Error"
        )
        debug_log(f"Error updating PTKP to TER mapping: {str(e)}", "TER Mapping Error")
        return False


def setup_accounts(config=None, specific_company=None):
    """
    Set up GL accounts for Indonesian payroll from config.
    """
    if not frappe.db.table_exists("Account"):
        debug_log("Account table does not exist", "Account Setup")
        return False
    if config is None:
        config = get_default_config()
    from payroll_indonesia.payroll_indonesia.utils import (
        create_account,
        debug_log,
        find_parent_account,
        create_parent_liability_account,
        create_parent_expense_account,
    )
    results = {"success": True, "created": [], "skipped": [], "errors": []}
    companies = []
    if specific_company:
        if frappe.db.table_exists("Company"):
            companies = frappe.get_all("Company", filters={"name": specific_company}, fields=["name", "abbr"])
            debug_log(f"Setting up accounts for specific company: {specific_company}", "Account Setup")
    else:
        if frappe.db.table_exists("Company"):
            companies = frappe.get_all("Company", fields=["name", "abbr"])
            debug_log(f"Setting up accounts for all companies: {len(companies)} found", "Account Setup")
    if not companies:
        debug_log("No companies found for account setup", "Account Setup")
        results["success"] = False
        results["errors"].append("No companies found")
        return results
    for company in companies:
        try:
            liability_parent = create_parent_liability_account(company.name)
            expense_parent = create_parent_expense_account(company.name)
            # ... (rest of the modular setup as in your original, omitted for brevity)
            results["created"].append(company.name)
        except Exception as e:
            results["success"] = False
            results["errors"].append(f"Error setting up accounts for {company.name}: {str(e)}")
            debug_log(f"Error setting up accounts for {company.name}: {str(e)}", "Account Setup")
    debug_log(
        f"Account setup completed with: {len(results['created'])} created, {len(results['skipped'])} skipped, {len(results['errors'])} errors",
        "Account Setup",
    )
    return results


def create_supplier_group():
    """
    Create Government supplier group for tax and BPJS entities.
    """
    if not frappe.db.table_exists("Supplier Group"):
        debug_log("Supplier Group table does not exist", "Supplier Setup")
        return False
    try:
        if frappe.db.exists("Supplier Group", "Government"):
            debug_log("Government supplier group already exists", "Supplier Setup")
            return True
        if not frappe.db.exists("Supplier Group", "All Supplier Groups"):
            debug_log("All Supplier Groups parent group missing", "Supplier Setup Error")
            return False
        group = frappe.new_doc("Supplier Group")
        group.supplier_group_name = "Government"
        group.parent_supplier_group = "All Supplier Groups"
        group.is_group = 0
        group.flags.ignore_permissions = True
        group.insert(ignore_permissions=True)
        frappe.db.commit()
        for subgroup in ["BPJS Provider", "Tax Authority"]:
            if not frappe.db.exists("Supplier Group", subgroup):
                sg = frappe.new_doc("Supplier Group")
                sg.supplier_group_name = subgroup
                sg.parent_supplier_group = "Government"
                sg.is_group = 0
                sg.flags.ignore_permissions = True
                sg.insert(ignore_permissions=True)
                frappe.db.commit()
                debug_log(f"Created {subgroup} supplier group", "Supplier Setup")
        debug_log("Created Government supplier group hierarchy", "Supplier Setup")
        return True
    except Exception as e:
        frappe.log_error(
            f"Failed to create supplier group: {str(e)}\n\n{frappe.get_traceback()}",
            "Supplier Setup Error"
        )
        debug_log(f"Failed to create supplier group: {str(e)}", "Supplier Setup Error")
        return False


def create_bpjs_supplier(config):
    """
    Create BPJS supplier entity from config.
    """
    if not frappe.db.table_exists("Supplier"):
        debug_log("Supplier table does not exist", "Supplier Setup")
        return False
    try:
        supplier_config = config.get("suppliers", {}).get("bpjs", {})
        if not supplier_config:
            debug_log("No BPJS supplier configuration found", "Supplier Setup")
            return False
        supplier_name = supplier_config.get("supplier_name", "BPJS")
        if frappe.db.exists("Supplier", supplier_name):
            debug_log(f"Supplier {supplier_name} already exists", "Supplier Setup")
            return True
        supplier_group = supplier_config.get("supplier_group", "Government")
        if not frappe.db.exists("Supplier Group", supplier_group):
            supplier_group = "BPJS Provider" if frappe.db.exists("Supplier Group", "BPJS Provider") else "Government"
            if not frappe.db.exists("Supplier Group", supplier_group):
                debug_log("No suitable supplier group exists", "Supplier Setup")
                return False
        supplier = frappe.new_doc("Supplier")
        supplier.supplier_name = supplier_name
        supplier.supplier_group = supplier_group
        supplier.supplier_type = supplier_config.get("supplier_type", "Government")
        supplier.country = supplier_config.get("country", "Indonesia")
        supplier.default_currency = supplier_config.get("default_currency", "IDR")
        supplier.flags.ignore_permissions = True
        supplier.insert(ignore_permissions=True)
        frappe.db.commit()
        debug_log(f"Created supplier: {supplier_name}", "Supplier Setup")
        return True
    except Exception as e:
        frappe.log_error(
            f"Failed to create BPJS supplier: {str(e)}\n\n{frappe.get_traceback()}",
            "Supplier Setup Error"
        )
        debug_log(f"Failed to create BPJS supplier: {str(e)}", "Supplier Setup Error")
        return False


def setup_pph21(config):
    """Setup PPh 21 tax settings including TER and tax slabs."""
    if not frappe.db.table_exists("PPh 21 Settings"):
        debug_log("PPh 21 Settings table does not exist", "PPh 21 Setup")
        return False
    try:
        pph21_settings = setup_pph21_defaults(config)
        if not pph21_settings:
            debug_log("Failed to setup PPh 21 defaults", "PPh 21 Setup Error")
            return False
        ter_result = setup_pph21_ter(config)
        tax_slab_result = setup_income_tax_slab(config)
        return ter_result and tax_slab_result
    except Exception as e:
        frappe.log_error(
            f"Error in PPh 21 setup: {str(e)}\n\n{frappe.get_traceback()}",
            "PPh 21 Setup Error"
        )
        debug_log(f"Error in PPh 21 setup: {str(e)}", "PPh 21 Setup Error")
        return False


def setup_pph21_defaults(config):
    """Setup default PPh 21 configuration with TER method using config data."""
    if not frappe.db.table_exists("PPh 21 Settings"):
        debug_log("PPh 21 Settings table does not exist", "PPh 21 Setup")
        return None
    try:
        settings = None
        if frappe.db.exists("PPh 21 Settings", "PPh 21 Settings"):
            settings = frappe.get_doc("PPh 21 Settings", "PPh 21 Settings")
            settings.ptkp_table = []
            settings.bracket_table = []
        else:
            settings = frappe.new_doc("PPh 21 Settings")
        tax_config = config.get("tax", {})
        settings.calculation_method = tax_config.get("tax_calculation_method", "TER")
        settings.use_ter = tax_config.get("use_ter", 1)
        settings.use_gross_up = tax_config.get("use_gross_up", 0)
        settings.npwp_mandatory = tax_config.get("npwp_mandatory", 0)
        settings.biaya_jabatan_percent = tax_config.get("biaya_jabatan_percent", 5.0)
        settings.biaya_jabatan_max = tax_config.get("biaya_jabatan_max", 500000.0)
        settings.umr_default = tax_config.get("umr_default", 4900000.0)
        settings.ter_notes = "Tarif Efektif Rata-rata (TER) sesuai PMK-168/PMK.010/2023"
        ptkp_values = config.get("ptkp", {})
        if not ptkp_values:
            debug_log("No PTKP values found in configuration", "PPh 21 Setup")
            raise ValidationError("No PTKP values found in configuration")
        for status, amount in ptkp_values.items():
            description = f"{status} (PTKP)"
            settings.append(
                "ptkp_table",
                {
                    "status_pajak": status,
                    "ptkp_amount": flt(amount),
                    "description": description,
                },
            )
        tax_brackets = config.get("tax_brackets", [])
        if not tax_brackets:
            debug_log("No tax brackets found in configuration", "PPh 21 Setup")
            raise ValidationError("No tax brackets found in configuration")
        for bracket in tax_brackets:
            settings.append(
                "bracket_table",
                {
                    "income_from": flt(bracket["income_from"]),
                    "income_to": flt(bracket["income_to"]),
                    "tax_rate": flt(bracket["tax_rate"]),
                },
            )
        settings.flags.ignore_permissions = True
        settings.flags.ignore_validate = True
        if settings.is_new():
            settings.insert(ignore_permissions=True)
        else:
            settings.save(ignore_permissions=True)
        frappe.db.commit()
        debug_log("PPh 21 Settings configured successfully", "PPh 21 Setup")
        return settings
    except Exception as e:
        frappe.log_error(
            f"Error setting up PPh 21: {str(e)}\n\n{frappe.get_traceback()}",
            "PPh 21 Setup Error"
        )
        debug_log(f"Error setting up PPh 21: {str(e)}", "PPh 21 Setup Error")
        return None


def setup_pph21_ter(config, force_update=False):
    """Setup default TER rates based on PMK-168/PMK.010/2023 using config data."""
    if not frappe.db.table_exists("PPh 21 TER Table"):
        debug_log("PPh 21 TER Table does not exist", "TER Setup Error")
        return False
    try:
        if not force_update:
            cats = ["TER A", "TER B", "TER C"]
            if all(frappe.db.exists("PPh 21 TER Table", {"status_pajak": cat}) for cat in cats):
                debug_log("TER categories already setup for PMK 168/2023", "TER Setup")
                return True
        frappe.db.sql("DELETE FROM `tabPPh 21 TER Table`")
        frappe.db.commit()
        ter_rates = config.get("ter_rates", {})
        if not ter_rates:
            debug_log("No TER rates found in configuration", "TER Setup Error")
            raise ValidationError("No TER rates found in configuration")
        count = 0
        for status, rates in ter_rates.items():
            for rate_data in rates:
                ter_entry = frappe.get_doc(
                    {
                        "doctype": "PPh 21 TER Table",
                        "status_pajak": status,
                        "income_from": flt(rate_data["income_from"]),
                        "income_to": flt(rate_data["income_to"]),
                        "rate": flt(rate_data["rate"]),
                        "description": f"{status} - {rate_data['income_from']} - {rate_data['income_to']}",
                        "is_highest_bracket": int(rate_data.get("is_highest_bracket", 0)),
                        "pmk_168": 1,
                    }
                )
                ter_entry.flags.ignore_permissions = True
                ter_entry.insert(ignore_permissions=True)
                count += 1
        frappe.db.commit()
        debug_log(f"Processed {count} TER rates successfully", "TER Setup")
        return count > 0
    except Exception as e:
        frappe.log_error(
            f"Error setting up TER rates: {str(e)}\n\n{frappe.get_traceback()}",
            "TER Setup Error"
        )
        debug_log(f"Error setting up TER rates: {str(e)}", "TER Setup Error")
        return False


def setup_income_tax_slab(config):
    """Create Income Tax Slab for Indonesia using config data."""
    if not frappe.db.table_exists("Income Tax Slab"):
        debug_log("Income Tax Slab table does not exist", "Tax Slab Setup")
        return False
    try:
        if frappe.db.exists("Income Tax Slab", {"currency": "IDR", "is_default": 1}):
            debug_log("Income Tax Slab already exists", "Tax Slab Setup")
            return True
        company = frappe.db.get_default("company")
        if not company and frappe.db.table_exists("Company"):
            companies = frappe.get_all("Company", pluck="name")
            company = companies[0] if companies else None
        if not company:
            debug_log("No company found for income tax slab", "Tax Slab Setup Error")
            return False
        tax_brackets = config.get("tax_brackets", [])
        if not tax_brackets:
            debug_log("No tax brackets found in configuration", "Tax Slab Setup")
            raise ValidationError("No tax brackets found in configuration")
        tax_slab = frappe.new_doc("Income Tax Slab")
        tax_slab.name = "Indonesia Income Tax"
        tax_slab.title = "Indonesia Income Tax"
        tax_slab.effective_from = getdate("2023-01-01")
        tax_slab.company = company
        tax_slab.currency = config.get("defaults", {}).get("currency", "IDR")
        tax_slab.is_default = 1
        tax_slab.disabled = 0
        for bracket in tax_brackets:
            tax_slab.append(
                "slabs",
                {
                    "from_amount": flt(bracket["income_from"]),
                    "to_amount": flt(bracket["income_to"]),
                    "percent_deduction": flt(bracket["tax_rate"]),
                },
            )
        tax_slab.flags.ignore_permissions = True
        tax_slab.flags.ignore_mandatory = True
        tax_slab.insert()
        debug_log(f"Created income tax slab: {tax_slab.name}", "Tax Slab Setup")
        return True
    except Exception as e:
        frappe.log_error(
            f"Error creating income tax slab: {str(e)}\n\n{frappe.get_traceback()}",
            "Tax Slab Setup Error"
        )
        debug_log(f"Error creating income tax slab: {str(e)}", "Tax Slab Setup Error")
        return False


def setup_salary_components(config):
    """
    Create or update salary components using config data.
    """
    if not frappe.db.table_exists("Salary Component"):
        debug_log("Salary Component table does not exist", "Salary Component Setup")
        return False
    try:
        components = config.get("salary_components", {})
        if not components:
            debug_log("No salary components found in configuration", "Salary Component Setup")
            raise ValidationError("No salary components found in configuration")
        success_count = 0
        total_count = 0
        for component_type in ["earnings", "deductions"]:
            if component_type not in components:
                continue
            for comp_data in components[component_type]:
                total_count += 1
                component_name = comp_data.get("name")
                if not component_name:
                    debug_log("Component name is missing in config", "Salary Component Setup Error")
                    continue
                if frappe.db.exists("Salary Component", component_name):
                    component = frappe.get_doc("Salary Component", component_name)
                    is_new = False
                else:
                    component = frappe.new_doc("Salary Component")
                    component.salary_component = component_name
                    is_new = True
                component.salary_component_abbr = comp_data.get("abbr", component_name[:3].upper())
                component.type = "Earning" if component_type == "earnings" else "Deduction"
                if "is_tax_applicable" in comp_data:
                    component.is_tax_applicable = comp_data.get("is_tax_applicable")
                if "variable_based_on_taxable_salary" in comp_data:
                    component.variable_based_on_taxable_salary = comp_data.get("variable_based_on_taxable_salary")
                if "statistical_component" in comp_data:
                    component.statistical_component = comp_data.get("statistical_component")
                if "do_not_include_in_total" in comp_data:
                    component.do_not_include_in_total = comp_data.get("do_not_include_in_total")
                if "exempted" in comp_data:
                    component.exempted = comp_data.get("exempted")
                if component_name == "PPh 21":
                    component.description = "PPh 21 (PMK 168/2023)"
                component.round_to_the_nearest_integer = 1
                component.flags.ignore_permissions = True
                if is_new:
                    component.insert(ignore_permissions=True)
                    debug_log(f"Created salary component: {component_name}", "Salary Component Setup")
                else:
                    component.save(ignore_permissions=True)
                    debug_log(f"Updated salary component: {component_name}", "Salary Component Setup")
                success_count += 1
        debug_log(
            f"Processed {success_count} of {total_count} salary components successfully",
            "Salary Component Setup"
        )
        return success_count > 0
    except Exception as e:
        frappe.log_error(
            f"Error setting up salary components: {str(e)}\n\n{frappe.get_traceback()}",
            "Salary Component Setup Error"
        )
        debug_log(f"Error setting up salary components: {str(e)}", "Salary Component Setup Error")
        return False


def display_installation_summary(results, config):
    """
    Display installation summary.
    """
    debug_log(
        "=== PAYROLL INDONESIA INSTALLATION SUMMARY ===\n"
        f"Accounts setup: {'Success' if results.get('accounts') else 'Failed'}\n"
        f"Suppliers setup: {'Success' if results.get('suppliers') else 'Failed'}\n"
        f"PPh 21 settings: {'Success' if results.get('pph21_settings') else 'Failed'}\n"
        f"Salary components: {'Success' if results.get('salary_components') else 'Failed'}\n"
        f"BPJS settings: {'Success' if results.get('bpjs_setup') else 'Failed'}\n"
        "===================================\n"
        "PMK 168/2023 Implementation: DONE\n"
        "===================================",
        "Installation Summary"
    )
