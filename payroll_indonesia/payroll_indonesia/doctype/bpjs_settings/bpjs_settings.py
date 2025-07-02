# -*- coding: utf-8 -*-
# Copyright (c) 2025, PT. Innovasi Terbaik Bangsa and contributors
# For license information, please see license.txt
# Last modified: 2025-07-02 15:28:12 by dannyaudian

"""
BPJS Settings DocType Controller

This module handles configuration settings for BPJS processing,
delegating validation to central validation helpers and syncing with configuration.
"""

import frappe
from frappe import _
from frappe.model.document import Document
import logging
from frappe.utils import now

# Configure logger
logger = logging.getLogger(__name__)


class BPJSSettings(Document):
    """
    DocType for managing BPJS Settings.

    This class handles configuration validation, data syncing between related
    DocTypes, and interfaces with the central configuration system.
    """

    def validate(self):
        """
        Validate settings on save.

        Validates field values and ensures data consistency.
        """
        if getattr(self, "_validated", False):
            return

        # Mark as being validated to prevent recursion
        self._validated = True

        try:
            # Validate data types and values
            self.validate_data_types()
            self.validate_percentages()
            self.validate_max_salary()
            self.validate_account_types()

            # Sync with main settings
            self.sync_with_payroll_settings()

            logger.info(f"Validated BPJS Settings")
        finally:
            # Always clean up flag
            self._validated = False

    def validate_data_types(self):
        """
        Validate that numeric fields contain valid numbers.
        """
        percentage_fields = [
            "kesehatan_employee_percent",
            "kesehatan_employer_percent",
            "jht_employee_percent",
            "jht_employer_percent",
            "jp_employee_percent",
            "jp_employer_percent",
            "jkk_percent",
            "jkm_percent",
        ]

        for field in percentage_fields:
            if hasattr(self, field) and self.get(field) is not None:
                try:
                    value = float(self.get(field))
                    if value < 0:
                        frappe.throw(_(f"{frappe.unscrub(field)} must be positive"))
                except (ValueError, TypeError):
                    frappe.throw(_(f"{frappe.unscrub(field)} must be a valid number"))

    def validate_percentages(self):
        """
        Validate that percentage fields have valid values.
        """
        # Get validation rules from configuration
        from payroll_indonesia.config.config import get_live_config

        config = get_live_config()
        validation_rules = config.get("bpjs_settings", {}).get("validation_rules", {})
        percentage_ranges = validation_rules.get("percentage_ranges", [])

        for rule in percentage_ranges:
            field = rule.get("field")
            min_val = rule.get("min", 0)
            max_val = rule.get("max", 100)
            error_msg = rule.get(
                "error_msg", f"{frappe.unscrub(field)} must be between {min_val} and {max_val}%"
            )

            if hasattr(self, field) and self.get(field) is not None:
                value = float(self.get(field))
                if value < min_val or value > max_val:
                    frappe.msgprint(_(error_msg), indicator="orange")

    def validate_max_salary(self):
        """
        Validate maximum salary thresholds.
        """
        # Get validation rules from configuration
        from payroll_indonesia.config.config import get_live_config

        config = get_live_config()
        validation_rules = config.get("bpjs_settings", {}).get("validation_rules", {})
        salary_thresholds = validation_rules.get("salary_thresholds", [])

        for rule in salary_thresholds:
            field = rule.get("field")
            min_val = rule.get("min", 0)
            error_msg = rule.get(
                "error_msg", f"{frappe.unscrub(field)} must be greater than {min_val}"
            )

            if hasattr(self, field) and self.get(field) is not None:
                value = float(self.get(field))
                if value < min_val:
                    frappe.msgprint(_(error_msg), indicator="orange")

    def validate_account_types(self):
        """
        Validate that account references have the correct type.
        """
        # Skip validation during initial setup/migration
        if not frappe.db.table_exists("Account"):
            return

        # Get account fields from configuration
        from payroll_indonesia.config.config import get_live_config

        config = get_live_config()
        account_fields = config.get("bpjs_settings", {}).get("account_fields", [])

        for field in account_fields:
            if hasattr(self, field) and self.get(field):
                account = self.get(field)
                if frappe.db.exists("Account", account):
                    acc_type = frappe.db.get_value("Account", account, "account_type")
                    if field.endswith("_account") and acc_type not in ["Payable", "Tax"]:
                        frappe.msgprint(
                            _(f"{frappe.unscrub(field)} should have account type Payable or Tax"),
                            indicator="orange",
                        )

    def setup_accounts(self):
        """
        Set up accounts for BPJS components.

        Creates or sets up the necessary accounts for BPJS processing.
        """
        if getattr(self, "_setup_running", False):
            return

        # Skip if tables don't exist yet
        if not frappe.db.table_exists("Account"):
            return

        # Mark as being set up to prevent recursion
        self._setup_running = True

        try:
            from payroll_indonesia.payroll_indonesia.doctype.bpjs_settings.utils import (
                create_parent_liability_account,
                create_parent_expense_account,
                create_account,
                debug_log,
            )

            debug_log("Setting up BPJS accounts", "BPJS Setup")

            # Create parent accounts
            parent_liability = create_parent_liability_account(self.company)
            parent_expense = create_parent_expense_account(self.company)

            # Setup BPJS accounts
            bpjs_accounts = {
                "kesehatan_account": "BPJS Kesehatan Payable",
                "jht_account": "BPJS JHT Payable",
                "jp_account": "BPJS JP Payable",
                "jkk_account": "BPJS JKK Payable",
                "jkm_account": "BPJS JKM Payable",
            }

            for field, acc_name in bpjs_accounts.items():
                if not self.get(field):
                    acc = create_account(self.company, acc_name, "Payable", parent_liability)
                    if acc:
                        self.set(field, acc)

            # Setup expense accounts
            expense_accounts = {
                "kesehatan_employer_expense": "BPJS Kesehatan Employer Expense",
                "jht_employer_expense": "BPJS JHT Employer Expense",
                "jp_employer_expense": "BPJS JP Employer Expense",
                "jkk_employer_expense": "BPJS JKK Employer Expense",
                "jkm_employer_expense": "BPJS JKM Employer Expense",
            }

            for field, acc_name in expense_accounts.items():
                if hasattr(self, field) and not self.get(field):
                    acc = create_account(self.company, acc_name, "Direct Expense", parent_expense)
                    if acc:
                        self.set(field, acc)

            # Save changes if any account was created
            self.db_update()
            debug_log("BPJS accounts setup completed", "BPJS Setup")

        finally:
            # Always clean up flag
            self._setup_running = False

    def sync_with_payroll_settings(self):
        """
        Sync with Payroll Indonesia Settings.

        Updates the main Payroll Indonesia Settings with BPJS values.
        """
        # Skip if Payroll Indonesia Settings table doesn't exist yet
        if not frappe.db.table_exists("Payroll Indonesia Settings"):
            return

        # Get Payroll Indonesia Settings
        if not frappe.db.exists("Payroll Indonesia Settings"):
            return

        pi_settings = frappe.get_doc("Payroll Indonesia Settings")
        if not pi_settings:
            return

        # Update fields
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
                and hasattr(self, field)
                and pi_settings.get(field) != self.get(field)
            ):
                pi_settings.set(field, self.get(field))
                needs_update = True

        if needs_update:
            pi_settings.app_last_updated = now()
            pi_settings.app_updated_by = frappe.session.user
            pi_settings.flags.ignore_validate = True
            pi_settings.flags.ignore_permissions = True
            pi_settings.save(ignore_permissions=True)
            logger.info("Updated Payroll Indonesia Settings with BPJS values")
