# -*- coding: utf-8 -*-
# Copyright (c) 2025, PT. Innovasi Terbaik Bangsa and contributors
# For license information, please see license.txt
# Last modified: 2025-07-02 16:36:23 by dannyaudian

"""
Settings Migration Module

Provides utility functions for migrating configuration settings from defaults.json
to Payroll Indonesia Settings document and its child tables.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, cast

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from payroll_indonesia.frappe_helpers import safe_execute, doc_exists

logger = logging.getLogger(__name__)


def migrate_ptkp_data(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate PTKP (non-taxable income) data from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not frappe.db.table_exists("PTKP Table Entry"):
        logger.warning(_("PTKP Table Entry table does not exist, skipping migration"))
        return False
        
    ptkp_data = config.get("ptkp", {})
    if not ptkp_data:
        logger.warning(_("No PTKP data found in configuration"))
        return False
        
    # Clear existing entries
    settings.ptkp_table = []
    
    # Add new entries
    for status_code, amount in ptkp_data.items():
        settings.append("ptkp_table", {
            "status_code": status_code,
            "amount": flt(amount)
        })
        
    logger.info(_("Migrated PTKP data: {0} entries").format(len(ptkp_data)))
    return True


def migrate_tax_brackets(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate tax brackets data from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not frappe.db.table_exists("Tax Bracket Entry"):
        logger.warning(_("Tax Bracket Entry table does not exist, skipping migration"))
        return False
        
    tax_brackets = config.get("tax_brackets", [])
    if not tax_brackets:
        logger.warning(_("No tax brackets found in configuration"))
        return False
        
    # Clear existing entries
    settings.tax_brackets = []
    
    # Add new entries
    for bracket in tax_brackets:
        settings.append("tax_brackets", {
            "income_from": flt(bracket.get("income_from", 0)),
            "income_to": flt(bracket.get("income_to", 0)),
            "tax_rate": flt(bracket.get("tax_rate", 0))
        })
        
    logger.info(_("Migrated tax brackets: {0} entries").format(len(tax_brackets)))
    return True


def migrate_ter_rates(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate TER (Tarif Efektif Rata-rata) rates from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not frappe.db.table_exists("TER Rate Category") or not frappe.db.table_exists("TER Rate Entry"):
        logger.warning(_("TER Rate tables do not exist, skipping migration"))
        return False
        
    ter_rates = config.get("ter_rates", {})
    if not ter_rates:
        logger.warning(_("No TER rates found in configuration"))
        return False
        
    # Clear existing entries
    settings.ter_rate_categories = []
    
    # Add metadata if available
    metadata = ter_rates.get("metadata", {})
    if metadata:
        settings.ter_regulation_ref = metadata.get("regulation_ref", "")
        settings.ter_effective_date = metadata.get("effective_date", "")
        settings.ter_description = metadata.get("description", "")
        settings.ter_default_category = metadata.get("default_category", "TER A")
        settings.ter_fallback_rate = flt(metadata.get("fallback_rate", 5.0))
    
    # Process each TER category
    for category_name, rates in ter_rates.items():
        # Skip metadata entry
        if category_name == "metadata":
            continue
            
        # Create TER category
        category = {
            "category_name": category_name,
            "ter_rates": []
        }
        
        # Add TER rates
        for rate in rates:
            category["ter_rates"].append({
                "income_from": flt(rate.get("income_from", 0)),
                "income_to": flt(rate.get("income_to", 0)),
                "rate": flt(rate.get("rate", 0)),
                "is_highest_bracket": rate.get("is_highest_bracket", 0)
            })
        
        settings.append("ter_rate_categories", category)
    
    logger.info(_("Migrated TER rates: {0} categories").format(len(ter_rates) - 
                                                              (1 if "metadata" in ter_rates else 0)))
    return True


def migrate_ptkp_ter_mapping(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate PTKP to TER mapping data from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not frappe.db.table_exists("PTKP TER Mapping Entry"):
        logger.warning(_("PTKP TER Mapping Entry table does not exist, skipping migration"))
        return False
        
    mapping_data = config.get("ptkp_to_ter_mapping", {})
    if not mapping_data:
        logger.warning(_("No PTKP to TER mapping found in configuration"))
        return False
        
    # Clear existing entries
    settings.ptkp_ter_mapping = []
    
    # Add new entries
    for ptkp_code, ter_category in mapping_data.items():
        settings.append("ptkp_ter_mapping", {
            "ptkp_code": ptkp_code,
            "ter_category": ter_category
        })
        
    logger.info(_("Migrated PTKP to TER mapping: {0} entries").format(len(mapping_data)))
    return True


def migrate_gl_accounts(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate GL account settings from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    gl_accounts = config.get("gl_accounts", {})
    if not gl_accounts:
        logger.warning(_("No GL accounts found in configuration"))
        return False
        
    # Set root account info
    root_account = gl_accounts.get("root_account", {})
    if root_account:
        settings.root_account_name = root_account.get("account_name", "Payroll Accounts")
        settings.root_account_type = root_account.get("account_type", "Group")
        settings.root_type = root_account.get("root_type", "Liability")
    
    # Set BPJS payable accounts
    bpjs_payable = gl_accounts.get("bpjs_payable_accounts", {})
    if bpjs_payable:
        settings.bpjs_jht_payable = bpjs_payable.get("bpjs_jht_payable", {}).get("account_name", "")
        settings.bpjs_jp_payable = bpjs_payable.get("bpjs_jp_payable", {}).get("account_name", "")
        settings.bpjs_kesehatan_payable = bpjs_payable.get("bpjs_kesehatan_payable", {}).get("account_name", "")
        settings.bpjs_jkk_payable = bpjs_payable.get("bpjs_jkk_payable", {}).get("account_name", "")
        settings.bpjs_jkm_payable = bpjs_payable.get("bpjs_jkm_payable", {}).get("account_name", "")
    
    # Set BPJS expense accounts
    bpjs_expense = gl_accounts.get("bpjs_expense_accounts", {})
    if bpjs_expense:
        settings.bpjs_jht_employer_expense = bpjs_expense.get("bpjs_jht_employer_expense", {}).get("account_name", "")
        settings.bpjs_jp_employer_expense = bpjs_expense.get("bpjs_jp_employer_expense", {}).get("account_name", "")
        settings.bpjs_kesehatan_employer_expense = bpjs_expense.get("bpjs_kesehatan_employer_expense", {}).get("account_name", "")
        settings.bpjs_jkk_employer_expense = bpjs_expense.get("bpjs_jkk_employer_expense", {}).get("account_name", "")
        settings.bpjs_jkm_employer_expense = bpjs_expense.get("bpjs_jkm_employer_expense", {}).get("account_name", "")
    
    # Set tax payable account
    payable_accounts = gl_accounts.get("payable_accounts", {})
    if payable_accounts:
        settings.tax_payable_account = payable_accounts.get("hutang_pph21", {}).get("account_name", "")
    
    logger.info(_("Migrated GL accounts configuration"))
    return True


def migrate_bpjs_rules(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate BPJS rules from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    bpjs_config = config.get("bpjs", {})
    if not bpjs_config:
        logger.warning(_("No BPJS configuration found in configuration"))
        return False
        
    # Set base BPJS percentages
    settings.kesehatan_employee_percent = flt(bpjs_config.get("kesehatan_employee_percent", 1.0))
    settings.kesehatan_employer_percent = flt(bpjs_config.get("kesehatan_employer_percent", 4.0))
    settings.kesehatan_max_salary = flt(bpjs_config.get("kesehatan_max_salary", 12000000.0))
    settings.jht_employee_percent = flt(bpjs_config.get("jht_employee_percent", 2.0))
    settings.jht_employer_percent = flt(bpjs_config.get("jht_employer_percent", 3.7))
    settings.jp_employee_percent = flt(bpjs_config.get("jp_employee_percent", 1.0))
    settings.jp_employer_percent = flt(bpjs_config.get("jp_employer_percent", 2.0))
    settings.jp_max_salary = flt(bpjs_config.get("jp_max_salary", 9077600.0))
    settings.jkk_percent = flt(bpjs_config.get("jkk_percent", 0.24))
    settings.jkm_percent = flt(bpjs_config.get("jkm_percent", 0.3))
    
    # Set BPJS validation limits
    validation_limits = bpjs_config.get("validation_limits", {})
    if validation_limits:
        settings.kesehatan_min_salary = flt(validation_limits.get("kesehatan_min_salary", 1000000.0))
        settings.kesehatan_max_salary = flt(validation_limits.get("kesehatan_max_salary", 12000000.0))
        settings.jp_min_salary = flt(validation_limits.get("jp_min_salary", 1000000.0))
        settings.jp_max_salary = flt(validation_limits.get("jp_max_salary", 9077600.0))
        settings.bpjs_calculation_precision = cint(validation_limits.get("calculation_precision", 2))
        settings.bpjs_rounding_method = validation_limits.get("rounding_method", "round")
    
    # Set BPJS GL accounts if available
    gl_accounts = bpjs_config.get("gl_accounts", {})
    if gl_accounts:
        settings.bpjs_payment_account = gl_accounts.get("payment_account", "")
        settings.bpjs_expense_account = gl_accounts.get("expense_account", "")
        settings.bpjs_kesehatan_account = gl_accounts.get("kesehatan_account", "")
        settings.bpjs_kesehatan_expense_account = gl_accounts.get("kesehatan_expense_account", "")
        settings.bpjs_jht_account = gl_accounts.get("jht_account", "")
        settings.bpjs_jht_expense_account = gl_accounts.get("jht_expense_account", "")
        settings.bpjs_jp_account = gl_accounts.get("jp_account", "")
        settings.bpjs_jp_expense_account = gl_accounts.get("jp_expense_account", "")
        settings.bpjs_jkk_account = gl_accounts.get("jkk_account", "")
        settings.bpjs_jkk_expense_account = gl_accounts.get("jkk_expense_account", "")
        settings.bpjs_jkm_account = gl_accounts.get("jkm_account", "")
        settings.bpjs_jkm_expense_account = gl_accounts.get("jkm_expense_account", "")
    
    logger.info(_("Migrated BPJS rules"))
    return True


def migrate_salary_structure(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate salary structure settings from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    struktur_gaji = config.get("struktur_gaji", {})
    if not struktur_gaji:
        logger.warning(_("No salary structure configuration found"))
        return False
        
    # Set salary structure defaults
    settings.basic_salary_percent = flt(struktur_gaji.get("basic_salary_percent", 75))
    settings.meal_allowance_default = flt(struktur_gaji.get("meal_allowance", 750000.0))
    settings.transport_allowance_default = flt(struktur_gaji.get("transport_allowance", 900000.0))
    settings.umr_default = flt(struktur_gaji.get("umr_default", 4900000.0))
    settings.position_allowance_percent = flt(struktur_gaji.get("position_allowance_percent", 7.5))
    settings.working_days_default = cint(struktur_gaji.get("hari_kerja_default", 22))
    
    # Set global defaults
    defaults = config.get("defaults", {})
    if defaults:
        settings.default_currency = defaults.get("currency", "IDR")
        settings.attendance_based_on_timesheet = cint(defaults.get("attendance_based_on_timesheet", 0))
        settings.payroll_frequency = defaults.get("payroll_frequency", "Monthly")
        settings.salary_slip_based_on = defaults.get("salary_slip_based_on", "Leave Policy")
        settings.max_working_days_per_month = cint(defaults.get("max_working_days_per_month", 22))
        settings.include_holidays_in_total_working_days = cint(defaults.get("include_holidays_in_total_working_days", 0))
        settings.working_hours_per_day = flt(defaults.get("working_hours_per_day", 8))
    
    logger.info(_("Migrated salary structure settings"))
    return True


def migrate_tax_settings(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate tax settings from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    tax_config = config.get("tax", {})
    if not tax_config:
        logger.warning(_("No tax configuration found"))
        return False
        
    # Set basic tax settings
    settings.umr_default = flt(tax_config.get("umr_default", 4900000.0))
    settings.biaya_jabatan_percent = flt(tax_config.get("biaya_jabatan_percent", 5.0))
    settings.biaya_jabatan_max = flt(tax_config.get("biaya_jabatan_max", 500000.0))
    settings.npwp_mandatory = cint(tax_config.get("npwp_mandatory", 0))
    settings.tax_calculation_method = tax_config.get("tax_calculation_method", "TER")
    settings.use_ter = cint(tax_config.get("use_ter", 1))
    settings.use_gross_up = cint(tax_config.get("use_gross_up", 0))
    
    # Set tax limits if available
    tax_limits = tax_config.get("limits", {})
    if tax_limits:
        settings.minimum_taxable_income = flt(tax_limits.get("minimum_taxable_income", 4500000.0))
        settings.maximum_non_taxable_pkp = flt(tax_limits.get("maximum_non_taxable_pkp", 54000000.0))
        settings.minimum_ptkp = flt(tax_limits.get("minimum_ptkp", 54000000.0))
        settings.maximum_tax_bracket = flt(tax_limits.get("maximum_tax_bracket", 5000000000.0))
        settings.highest_tax_rate = flt(tax_limits.get("highest_tax_rate", 35.0))
        settings.biaya_jabatan_min = flt(tax_limits.get("biaya_jabatan_min", 0.0))
        settings.biaya_jabatan_max = flt(tax_limits.get("biaya_jabatan_max", 500000.0))
        settings.biaya_jabatan_percent_max = flt(tax_limits.get("biaya_jabatan_percent_max", 5.0))
        settings.tax_rounding_precision = cint(tax_limits.get("rounding_precision", 2))
    
    logger.info(_("Migrated tax settings"))
    return True


def migrate_employee_types(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate employee types from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not frappe.db.table_exists("Tipe Karyawan Entry"):
        logger.warning(_("Tipe Karyawan Entry table does not exist, skipping migration"))
        return False
        
    tipe_karyawan = config.get("tipe_karyawan", [])
    if not tipe_karyawan:
        logger.warning(_("No employee types found in configuration"))
        return False
        
    # Clear existing entries
    settings.tipe_karyawan = []
    
    # Add new entries
    for tipe in tipe_karyawan:
        settings.append("tipe_karyawan", {
            "tipe": tipe
        })
        
    logger.info(_("Migrated employee types: {0} entries").format(len(tipe_karyawan)))
    return True


def migrate_all_settings(settings: "frappe.Document", config: Dict[str, Any]) -> Dict[str, bool]:
    """
    Migrate all settings from config to Payroll Indonesia Settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        Dict[str, bool]: Status of each migration section
    """
    results = {
        "ptkp_data": migrate_ptkp_data(settings, config),
        "tax_brackets": migrate_tax_brackets(settings, config),
        "ter_rates": migrate_ter_rates(settings, config),
        "ptkp_ter_mapping": migrate_ptkp_ter_mapping(settings, config),
        "gl_accounts": migrate_gl_accounts(settings, config),
        "bpjs_rules": migrate_bpjs_rules(settings, config),
        "salary_structure": migrate_salary_structure(settings, config),
        "tax_settings": migrate_tax_settings(settings, config),
        "employee_types": migrate_employee_types(settings, config)
    }
    
    # Set app info
    app_info = config.get("app_info", {})
    settings.app_version = app_info.get("version", "1.0.0")
    settings.app_last_updated = app_info.get("last_updated", now_datetime())
    settings.app_updated_by = app_info.get("updated_by", frappe.session.user)
    
    # Set enabled flag
    settings.enabled = 1
    
    return results


def cint(value: Any) -> int:
    """Convert value to integer safely."""
    try:
        return int(value or 0)
    except (ValueError, TypeError):
        return 0
