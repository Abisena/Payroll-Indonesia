# -*- coding: utf-8 -*-
# Copyright (c) 2025, PT. Innovasi Terbaik Bangsa and contributors
# For license information, please see license.txt
# Last modified: 2025-07-02 13:18:02 by dannyaudian

"""
This module is a compatibility layer that forwards utility functions
from the central utils module to maintain backward compatibility.
"""

# FIXED: Use correct import path for get_default_config
from payroll_indonesia.config.config import get_config as get_default_config

# Import other utility functions
from payroll_indonesia.payroll_indonesia.utils import (
    get_settings,
    debug_log,
    find_parent_account,
    create_account,
    create_parent_liability_account,
    create_parent_expense_account,
    retry_bpjs_mapping,
)

__all__ = [
    "validate_settings",
    "setup_accounts",
    "get_settings",
    "get_default_config",
    "find_parent_account",
    "create_account",
    "create_parent_liability_account",
    "create_parent_expense_account",
    "retry_bpjs_mapping",
    "debug_log",
]


# Validation functions for hooks.py - keep these as they're specific to BPJS Settings
def validate_settings(doc, method=None):
    """Wrapper for BPJSSettings.validate method with protection against recursion"""
    # Skip if already being validated
    if getattr(doc, "_validated", False):
        return

    # Mark as being validated to prevent recursion
    doc._validated = True

    try:
        # Call the instance methods
        doc.validate_data_types()
        doc.validate_percentages()
        doc.validate_max_salary()
        doc.validate_account_types()

        # Sync with Payroll Indonesia Settings
        sync_with_payroll_settings(doc)
    finally:
        # Always clean up flag
        doc._validated = False


def setup_accounts(doc, method=None):
    """Wrapper for BPJSSettings.setup_accounts method with protection against recursion"""
    # Skip if already being processed
    if getattr(doc, "_setup_running", False):
        return

    # Mark as being processed to prevent recursion
    doc._setup_running = True

    try:
        # Call the instance method
        doc.setup_accounts()
    finally:
        # Always clean up flag
        doc._setup_running = False


def sync_with_payroll_settings(bpjs_doc):
    """
    Sync BPJS Settings with Payroll Indonesia Settings

    Args:
        bpjs_doc: BPJS Settings document
    """
    try:
        # Check if Payroll Indonesia Settings exists
        if not bpjs_doc:
            return

        if not hasattr(bpjs_doc, "kesehatan_employee_percent"):
            return

        # Get central settings
        pi_settings = get_settings()

        # Update Payroll Indonesia Settings with BPJS values
        fields_to_update = [
            "kesehatan_employee_percent",
            "kesehatan_employer_percent",
            "kesehatan_max_salary",
            "jht_employee_percent",
            "jht_employer_percent",
            "jp_employee_percent",
            "jp_employer_percent",
            "jp_max_salary",
            "jkk_percent",
            "jkm_percent",
        ]

        needs_update = False
        for field in fields_to_update:
            if (
                hasattr(pi_settings, field)
                and hasattr(bpjs_doc, field)
                and pi_settings.get(field) != bpjs_doc.get(field)
            ):
                pi_settings.set(field, bpjs_doc.get(field))
                needs_update = True

        if needs_update:
            pi_settings.app_last_updated = "2025-07-02 13:18:02"
            pi_settings.app_updated_by = "dannyaudian"
            pi_settings.flags.ignore_validate = True
            pi_settings.flags.ignore_permissions = True
            pi_settings.save(ignore_permissions=True)
            debug_log("Payroll Indonesia Settings updated with BPJS values", "BPJS Settings Sync")
    except Exception as e:
        debug_log(
            f"Error syncing BPJS Settings to Payroll Indonesia Settings: {str(e)}",
            "BPJS Settings Sync"
        )
