# -*- coding: utf-8 -*-
# Copyright (c) 2025, PT. Innovasi Terbaik Bangsa and contributors
# For license information, please see license.txt
# Last modified: 2025-07-02 16:49:17 by dannyaudian

"""
Settings Migration Module

Provides utility functions for migrating configuration settings from defaults.json
to Payroll Indonesia Settings document and its child tables.
"""

import logging
import json
from typing import Any, Dict, List, Optional, Tuple, cast

import frappe
from frappe import _
from frappe.utils import flt, cint, now_datetime

logger = logging.getLogger(__name__)


def debug_log(message: str, level: str = "info") -> None:
    """
    Log message with appropriate level.
    
    Args:
        message: Message to log
        level: Log level (debug, info, warning, error)
    """
    if level == "debug":
        logger.debug(message)
    elif level == "info":
        logger.info(message)
    elif level == "warning":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    else:
        logger.info(message)


def migrate_ptkp(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate PTKP (non-taxable income) data from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if table exists in DocType
        if not hasattr(settings, "ptkp_table"):
            debug_log("ptkp_table child table not found in Payroll Indonesia Settings", "warning")
            return False
        
        # Extract PTKP data from config
        ptkp_data = config.get("ptkp", {})
        if not ptkp_data:
            debug_log("No PTKP data found in configuration", "warning")
            return False
        
        # Clear existing entries
        settings.ptkp_table = []
        
        # Add new entries
        count = 0
        for status_code, amount in ptkp_data.items():
            settings.append("ptkp_table", {
                "status_code": status_code,
                "amount": flt(amount)
            })
            count += 1
        
        # Alternative JSON backup if table insertion fails
        try:
            # Store as JSON if field exists
            if hasattr(settings, "ptkp_json"):
                settings.ptkp_json = json.dumps(ptkp_data)
        except Exception as e:
            debug_log(f"Could not store PTKP as JSON backup: {str(e)}", "warning")
        
        debug_log(f"Migrated PTKP data: {count} entries")
        return True
        
    except Exception as e:
        debug_log(f"Error migrating PTKP data: {str(e)}", "error")
        return False


def migrate_tax_brackets(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate tax brackets data from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if table exists in DocType
        if not hasattr(settings, "tax_brackets_table"):
            debug_log("tax_brackets_table child table not found in Payroll Indonesia Settings", "warning")
            return False
        
        # Extract tax brackets from config
        tax_brackets = config.get("tax_brackets", [])
        if not tax_brackets:
            debug_log("No tax brackets found in configuration", "warning")
            return False
        
        # Clear existing entries
        settings.tax_brackets_table = []
        
        # Add new entries
        count = 0
        for bracket in tax_brackets:
            settings.append("tax_brackets_table", {
                "income_from": flt(bracket.get("income_from", 0)),
                "income_to": flt(bracket.get("income_to", 0)),
                "tax_rate": flt(bracket.get("tax_rate", 0))
            })
            count += 1
        
        # Alternative JSON backup if table insertion fails
        try:
            # Store as JSON if field exists
            if hasattr(settings, "tax_brackets_json"):
                settings.tax_brackets_json = json.dumps(tax_brackets)
        except Exception as e:
            debug_log(f"Could not store tax brackets as JSON backup: {str(e)}", "warning")
        
        debug_log(f"Migrated tax brackets: {count} entries")
        return True
        
    except Exception as e:
        debug_log(f"Error migrating tax brackets: {str(e)}", "error")
        return False


def migrate_ter_rates(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate TER (Tarif Efektif Rata-rata) rates from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Extract TER rates from config
        ter_rates = config.get("ter_rates", {})
        if not ter_rates:
            debug_log("No TER rates found in configuration", "warning")
            return False
        
        # Check if primary table exists in DocType
        has_primary_table = hasattr(settings, "ter_rates_table")
        
        # Check if backup JSON fields exist
        has_json_backup = (
            hasattr(settings, "ter_rate_ter_a_json") or
            hasattr(settings, "ter_rate_ter_b_json") or
            hasattr(settings, "ter_rate_ter_c_json")
        )
        
        if not has_primary_table and not has_json_backup:
            debug_log("Neither ter_rates_table nor JSON backup fields found", "warning")
            return False
        
        # Add metadata if available
        metadata = ter_rates.get("metadata", {})
        if metadata:
            if hasattr(settings, "ter_regulation_ref"):
                settings.ter_regulation_ref = metadata.get("regulation_ref", "")
            
            if hasattr(settings, "ter_effective_date"):
                settings.ter_effective_date = metadata.get("effective_date", "")
            
            if hasattr(settings, "ter_description"):
                settings.ter_description = metadata.get("description", "")
            
            if hasattr(settings, "ter_default_category"):
                settings.ter_default_category = metadata.get("default_category", "TER A")
            
            if hasattr(settings, "ter_fallback_rate"):
                settings.ter_fallback_rate = flt(metadata.get("fallback_rate", 5.0))
        
        # Process TER A, B, C rates
        if "TER A" in ter_rates and hasattr(settings, "ter_rate_ter_a_json"):
            settings.ter_rate_ter_a_json = json.dumps(ter_rates["TER A"])
            debug_log("Stored TER A rates in JSON field")
        
        if "TER B" in ter_rates and hasattr(settings, "ter_rate_ter_b_json"):
            settings.ter_rate_ter_b_json = json.dumps(ter_rates["TER B"])
            debug_log("Stored TER B rates in JSON field")
        
        if "TER C" in ter_rates and hasattr(settings, "ter_rate_ter_c_json"):
            settings.ter_rate_ter_c_json = json.dumps(ter_rates["TER C"])
            debug_log("Stored TER C rates in JSON field")
        
        # If we have the primary table, populate it
        if has_primary_table:
            # Clear existing entries
            settings.ter_rates_table = []
            
            # Process each TER category
            count = 0
            for category_name, rates in ter_rates.items():
                # Skip metadata entry
                if category_name == "metadata":
                    continue
                
                # Add each rate in the category
                for rate in rates:
                    settings.append("ter_rates_table", {
                        "category": category_name,
                        "income_from": flt(rate.get("income_from", 0)),
                        "income_to": flt(rate.get("income_to", 0)),
                        "rate": flt(rate.get("rate", 0)),
                        "is_highest_bracket": cint(rate.get("is_highest_bracket", 0))
                    })
                    count += 1
            
            debug_log(f"Migrated TER rates: {count} entries across all categories")
        
        return True
        
    except Exception as e:
        debug_log(f"Error migrating TER rates: {str(e)}", "error")
        return False


def migrate_gl_accounts(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate GL account settings from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Extract GL accounts from config
        gl_accounts = config.get("gl_accounts", {})
        if not gl_accounts:
            debug_log("No GL accounts found in configuration", "warning")
            return False
        
        # Set root account info
        root_account = gl_accounts.get("root_account", {})
        if root_account:
            if hasattr(settings, "root_account_name"):
                settings.root_account_name = root_account.get("account_name", "Payroll Accounts")
            
            if hasattr(settings, "root_account_type"):
                settings.root_account_type = root_account.get("account_type", "Group")
            
            if hasattr(settings, "root_type"):
                settings.root_type = root_account.get("root_type", "Liability")
        
        # Set BPJS payable accounts
        bpjs_payable = gl_accounts.get("bpjs_payable_accounts", {})
        if bpjs_payable:
            account_mappings = [
                ("bpjs_jht_payable", "bpjs_jht_payable"),
                ("bpjs_jp_payable", "bpjs_jp_payable"),
                ("bpjs_kesehatan_payable", "bpjs_kesehatan_payable"),
                ("bpjs_jkk_payable", "bpjs_jkk_payable"),
                ("bpjs_jkm_payable", "bpjs_jkm_payable")
            ]
            
            for setting_field, config_key in account_mappings:
                if hasattr(settings, setting_field) and config_key in bpjs_payable:
                    account_info = bpjs_payable.get(config_key, {})
                    setattr(settings, setting_field, account_info.get("account_name", ""))
        
        # Set BPJS expense accounts
        bpjs_expense = gl_accounts.get("bpjs_expense_accounts", {})
        if bpjs_expense:
            expense_mappings = [
                ("bpjs_jht_employer_expense", "bpjs_jht_employer_expense"),
                ("bpjs_jp_employer_expense", "bpjs_jp_employer_expense"),
                ("bpjs_kesehatan_employer_expense", "bpjs_kesehatan_employer_expense"),
                ("bpjs_jkk_employer_expense", "bpjs_jkk_employer_expense"),
                ("bpjs_jkm_employer_expense", "bpjs_jkm_employer_expense")
            ]
            
            for setting_field, config_key in expense_mappings:
                if hasattr(settings, setting_field) and config_key in bpjs_expense:
                    account_info = bpjs_expense.get(config_key, {})
                    setattr(settings, setting_field, account_info.get("account_name", ""))
        
        # Set tax payable account
        payable_accounts = gl_accounts.get("payable_accounts", {})
        if payable_accounts and hasattr(settings, "tax_payable_account"):
            tax_account = payable_accounts.get("hutang_pph21", {})
            settings.tax_payable_account = tax_account.get("account_name", "")
        
        debug_log("Migrated GL accounts configuration")
        return True
        
    except Exception as e:
        debug_log(f"Error migrating GL accounts: {str(e)}", "error")
        return False


def migrate_bpjs_rules(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate BPJS rules from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Extract BPJS config from config
        bpjs_config = config.get("bpjs", {})
        if not bpjs_config:
            debug_log("No BPJS configuration found", "warning")
            return False
        
        # Define field mappings
        percent_fields = [
            ("kesehatan_employee_percent", 1.0),
            ("kesehatan_employer_percent", 4.0),
            ("jht_employee_percent", 2.0),
            ("jht_employer_percent", 3.7),
            ("jp_employee_percent", 1.0),
            ("jp_employer_percent", 2.0),
            ("jkk_percent", 0.24),
            ("jkm_percent", 0.3)
        ]
        
        # Set percentage fields
        for field_name, default_value in percent_fields:
            if hasattr(settings, field_name):
                setattr(settings, field_name, flt(bpjs_config.get(field_name, default_value)))
        
        # Set salary threshold fields
        if hasattr(settings, "kesehatan_max_salary"):
            settings.kesehatan_max_salary = flt(bpjs_config.get("kesehatan_max_salary", 12000000.0))
        
        if hasattr(settings, "jp_max_salary"):
            settings.jp_max_salary = flt(bpjs_config.get("jp_max_salary", 9077600.0))
        
        # Set BPJS validation limits
        validation_limits = bpjs_config.get("validation_limits", {})
        if validation_limits:
            limit_fields = [
                ("kesehatan_min_salary", 1000000.0),
                ("kesehatan_max_salary", 12000000.0),
                ("jp_min_salary", 1000000.0),
                ("jp_max_salary", 9077600.0)
            ]
            
            for field_name, default_value in limit_fields:
                if hasattr(settings, field_name):
                    setattr(settings, field_name, flt(validation_limits.get(field_name, default_value)))
            
            # Set calculation precision and rounding method
            if hasattr(settings, "bpjs_calculation_precision"):
                settings.bpjs_calculation_precision = cint(validation_limits.get("calculation_precision", 2))
            
            if hasattr(settings, "bpjs_rounding_method"):
                settings.bpjs_rounding_method = validation_limits.get("rounding_method", "round")
        
        # Set BPJS GL accounts if available
        gl_accounts = bpjs_config.get("gl_accounts", {})
        if gl_accounts:
            account_mappings = [
                ("bpjs_payment_account", "payment_account"),
                ("bpjs_expense_account", "expense_account"),
                ("bpjs_kesehatan_account", "kesehatan_account"),
                ("bpjs_kesehatan_expense_account", "kesehatan_expense_account"),
                ("bpjs_jht_account", "jht_account"),
                ("bpjs_jht_expense_account", "jht_expense_account"),
                ("bpjs_jp_account", "jp_account"),
                ("bpjs_jp_expense_account", "jp_expense_account"),
                ("bpjs_jkk_account", "jkk_account"),
                ("bpjs_jkk_expense_account", "jkk_expense_account"),
                ("bpjs_jkm_account", "jkm_account"),
                ("bpjs_jkm_expense_account", "jkm_expense_account")
            ]
            
            for setting_field, config_key in account_mappings:
                if hasattr(settings, setting_field) and config_key in gl_accounts:
                    setattr(settings, setting_field, gl_accounts.get(config_key, ""))
        
        debug_log("Migrated BPJS rules")
        return True
        
    except Exception as e:
        debug_log(f"Error migrating BPJS rules: {str(e)}", "error")
        return False


def migrate_salary_structure(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate salary structure settings from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Extract salary structure from config
        struktur_gaji = config.get("struktur_gaji", {})
        if not struktur_gaji:
            debug_log("No salary structure configuration found", "warning")
            return False
        
        # Define field mappings with defaults
        field_mappings = [
            ("basic_salary_percent", "basic_salary_percent", 75),
            ("meal_allowance_default", "meal_allowance", 750000.0),
            ("transport_allowance_default", "transport_allowance", 900000.0),
            ("umr_default", "umr_default", 4900000.0),
            ("position_allowance_percent", "position_allowance_percent", 7.5),
            ("working_days_default", "hari_kerja_default", 22)
        ]
        
        # Set salary structure fields
        for setting_field, config_key, default_value in field_mappings:
            if hasattr(settings, setting_field):
                if config_key in struktur_gaji:
                    if setting_field == "working_days_default":
                        setattr(settings, setting_field, cint(struktur_gaji.get(config_key, default_value)))
                    else:
                        setattr(settings, setting_field, flt(struktur_gaji.get(config_key, default_value)))
        
        # Set global defaults
        defaults = config.get("defaults", {})
        if defaults:
            default_mappings = [
                ("default_currency", "currency", "IDR", str),
                ("attendance_based_on_timesheet", "attendance_based_on_timesheet", 0, cint),
                ("payroll_frequency", "payroll_frequency", "Monthly", str),
                ("salary_slip_based_on", "salary_slip_based_on", "Leave Policy", str),
                ("max_working_days_per_month", "max_working_days_per_month", 22, cint),
                ("include_holidays_in_total_working_days", "include_holidays_in_total_working_days", 0, cint),
                ("working_hours_per_day", "working_hours_per_day", 8, flt)
            ]
            
            for setting_field, config_key, default_value, convert_func in default_mappings:
                if hasattr(settings, setting_field) and config_key in defaults:
                    setattr(settings, setting_field, convert_func(defaults.get(config_key, default_value)))
        
        debug_log("Migrated salary structure settings")
        return True
        
    except Exception as e:
        debug_log(f"Error migrating salary structure: {str(e)}", "error")
        return False


def migrate_ptkp_ter_mapping(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate PTKP to TER mapping data from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if table exists in DocType
        if not hasattr(settings, "ptkp_ter_mapping_table"):
            debug_log("ptkp_ter_mapping_table child table not found in Payroll Indonesia Settings", "warning")
            return False
        
        # Extract mapping data from config
        mapping_data = config.get("ptkp_to_ter_mapping", {})
        if not mapping_data:
            debug_log("No PTKP to TER mapping found in configuration", "warning")
            return False
        
        # Clear existing entries
        settings.ptkp_ter_mapping_table = []
        
        # Add new entries
        count = 0
        for ptkp_code, ter_category in mapping_data.items():
            settings.append("ptkp_ter_mapping_table", {
                "ptkp_code": ptkp_code,
                "ter_category": ter_category
            })
            count += 1
        
        # Alternative JSON backup if table insertion fails
        try:
            # Store as JSON if field exists
            if hasattr(settings, "ptkp_ter_mapping_json"):
                settings.ptkp_ter_mapping_json = json.dumps(mapping_data)
        except Exception as e:
            debug_log(f"Could not store PTKP to TER mapping as JSON backup: {str(e)}", "warning")
        
        debug_log(f"Migrated PTKP to TER mapping: {count} entries")
        return True
        
    except Exception as e:
        debug_log(f"Error migrating PTKP to TER mapping: {str(e)}", "error")
        return False


def migrate_tax_settings(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate tax settings from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Extract tax config from config
        tax_config = config.get("tax", {})
        if not tax_config:
            debug_log("No tax configuration found", "warning")
            return False
        
        # Define field mappings with defaults
        field_mappings = [
            ("umr_default", "umr_default", 4900000.0, flt),
            ("biaya_jabatan_percent", "biaya_jabatan_percent", 5.0, flt),
            ("biaya_jabatan_max", "biaya_jabatan_max", 500000.0, flt),
            ("npwp_mandatory", "npwp_mandatory", 0, cint),
            ("tax_calculation_method", "tax_calculation_method", "TER", str),
            ("use_ter", "use_ter", 1, cint),
            ("use_gross_up", "use_gross_up", 0, cint)
        ]
        
        # Set tax settings fields
        for setting_field, config_key, default_value, convert_func in field_mappings:
            if hasattr(settings, setting_field) and config_key in tax_config:
                setattr(settings, setting_field, convert_func(tax_config.get(config_key, default_value)))
        
        # Set tax limits if available
        tax_limits = tax_config.get("limits", {})
        if tax_limits:
            limit_mappings = [
                ("minimum_taxable_income", 4500000.0),
                ("maximum_non_taxable_pkp", 54000000.0),
                ("minimum_ptkp", 54000000.0),
                ("maximum_tax_bracket", 5000000000.0),
                ("highest_tax_rate", 35.0),
                ("biaya_jabatan_min", 0.0),
                ("biaya_jabatan_max", 500000.0),
                ("biaya_jabatan_percent_max", 5.0),
                ("tax_rounding_precision", 2)
            ]
            
            for field_name, default_value in limit_mappings:
                if hasattr(settings, field_name):
                    if field_name == "tax_rounding_precision":
                        setattr(settings, field_name, cint(tax_limits.get(field_name, default_value)))
                    else:
                        setattr(settings, field_name, flt(tax_limits.get(field_name, default_value)))
        
        debug_log("Migrated tax settings")
        return True
        
    except Exception as e:
        debug_log(f"Error migrating tax settings: {str(e)}", "error")
        return False


def migrate_employee_types(settings: "frappe.Document", config: Dict[str, Any]) -> bool:
    """
    Migrate employee types from config to settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if table exists in DocType
        if not hasattr(settings, "tipe_karyawan_table"):
            debug_log("tipe_karyawan_table child table not found in Payroll Indonesia Settings", "warning")
            return False
        
        # Extract employee types from config
        tipe_karyawan = config.get("tipe_karyawan", [])
        if not tipe_karyawan:
            debug_log("No employee types found in configuration", "warning")
            return False
        
        # Clear existing entries
        settings.tipe_karyawan_table = []
        
        # Add new entries
        count = 0
        for tipe in tipe_karyawan:
            settings.append("tipe_karyawan_table", {
                "tipe": tipe
            })
            count += 1
        
        # Alternative JSON backup if table insertion fails
        try:
            # Store as JSON if field exists
            if hasattr(settings, "tipe_karyawan_json"):
                settings.tipe_karyawan_json = json.dumps(tipe_karyawan)
        except Exception as e:
            debug_log(f"Could not store employee types as JSON backup: {str(e)}", "warning")
        
        debug_log(f"Migrated employee types: {count} entries")
        return True
        
    except Exception as e:
        debug_log(f"Error migrating employee types: {str(e)}", "error")
        return False


def migrate_all_settings(settings: "frappe.Document", config: Dict[str, Any]) -> Dict[str, bool]:
    """
    Migrate all settings from config to Payroll Indonesia Settings.
    
    Args:
        settings: Payroll Indonesia Settings document
        config: Configuration dictionary
        
    Returns:
        Dict[str, bool]: Status of each migration section
    """
    debug_log("Starting migration of all settings to Payroll Indonesia Settings")
    
    # Migrate each section
    results = {
        "ptkp_data": migrate_ptkp(settings, config),
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
    if hasattr(settings, "app_version"):
        settings.app_version = app_info.get("version", "1.0.0")
    
    if hasattr(settings, "app_last_updated"):
        settings.app_last_updated = app_info.get("last_updated", now_datetime())
    
    if hasattr(settings, "app_updated_by"):
        settings.app_updated_by = app_info.get("updated_by", frappe.session.user)
    
    # Set enabled flag
    if hasattr(settings, "enabled"):
        settings.enabled = 1
    
    # Log the results
    succeeded = sum(1 for result in results.values() if result)
    failed = len(results) - succeeded
    
    debug_log(f"Migration completed: {succeeded}/{len(results)} sections migrated successfully")
    
    if failed > 0:
        debug_log(f"Failed to migrate {failed} sections", "warning")
        
        # Log the failed sections
        for section, success in results.items():
            if not success:
                debug_log(f"Failed to migrate section: {section}", "warning")
    
    return results
