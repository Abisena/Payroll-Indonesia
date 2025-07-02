# -*- coding: utf-8 -*-
# Copyright (c) 2025, PT. Innovasi Terbaik Bangsa and contributors
# For license information, please see license.txt
# Last modified: 2025-07-02 16:52:03 by dannyaudian

"""
Payroll Indonesia Settings DocType Controller

This module handles configuration settings for Indonesian Payroll processing,
delegating validation to central validation helpers and syncing with configuration.
"""

import json
import logging
from typing import Dict, List, Any

# from typing import Dict, List, Any, Optional

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, cint, now

from payroll_indonesia.config.config import get_config, get_live_config
from payroll_indonesia.payroll_indonesia.validations import (
    validate_bpjs_components,
)
from payroll_indonesia.frappe_helpers import safe_execute

# Configure logger
logger = logging.getLogger(__name__)


class PayrollIndonesiaSettings(Document):
    """
    DocType for managing Payroll Indonesia Settings.

    This class handles configuration validation, data syncing between related
    DocTypes, and interfaces with the central configuration system.
    """

    def validate(self) -> None:
        """
        Validate settings on save.

        Delegates validation to central validation helpers and performs minimal
        local validation for configuration integrity.
        """
        try:
            # Update timestamp for audit
            self.app_last_updated = now()
            self.app_updated_by = frappe.session.user

            # Perform validations using central validation system
            self._validate_tax_settings()
            self._validate_bpjs_settings()
            self._validate_json_fields()

            # Sync settings to related doctypes
            self._sync_to_related_doctypes()

            logger.info(f"Validated Payroll Indonesia Settings by {self.app_updated_by}")

        except Exception as e:
            logger.error(f"Error validating Payroll Indonesia Settings: {str(e)}")
            frappe.log_error(
                f"Error validating Payroll Indonesia Settings: {str(e)}", "Settings Error"
            )

    def before_save(self) -> None:
        """
        Perform actions before saving the document.

        Optionally syncs settings to defaults.json if configured to do so.
        """
        # Check if sync to defaults.json is enabled
        config = get_live_config()
        sync_to_defaults = config.get("settings", {}).get("sync_to_defaults", False)

        if sync_to_defaults:
            self._sync_to_defaults_json()

    def on_update(self) -> None:
        """
        Perform actions after document is updated.

        Populates default values if needed and ensures required data exists.
        """
        self._populate_default_values()

    @safe_execute(log_exception=True)
    def _validate_tax_settings(self) -> None:
        """
        Validate tax-related settings.

        Ensures required tax configuration tables are properly defined.
        """
        # Only validate if the tables exist
        if not frappe.db.table_exists("Payroll Indonesia Settings"):
            logger.warning("Payroll Indonesia Settings table does not exist yet")
            return

        if hasattr(self, "ptkp_table") and not self.ptkp_table:
            frappe.msgprint(
                _("PTKP values must be defined for tax calculation"), indicator="orange"
            )

        if (
            self.use_ter
            and hasattr(self, "ptkp_ter_mapping_table")
            and not self.ptkp_ter_mapping_table
        ):
            frappe.msgprint(
                _("PTKP to TER mappings should be defined when using TER calculation method"),
                indicator="orange",
            )

        # Validate tax brackets
        if hasattr(self, "tax_brackets_table") and not self.tax_brackets_table:
            frappe.msgprint(
                _("Tax brackets should be defined for tax calculation"), indicator="orange"
            )

        # Get config limits
        config = get_live_config()
        tax_limits = config.get("tax", {}).get("limits", {})

        # Validate biaya jabatan percent is within limits
        min_biaya_jabatan = tax_limits.get("min_biaya_jabatan_percent", 0)
        max_biaya_jabatan = tax_limits.get("max_biaya_jabatan_percent", 10)

        if hasattr(self, "biaya_jabatan_percent"):
            if (
                self.biaya_jabatan_percent < min_biaya_jabatan
                or self.biaya_jabatan_percent > max_biaya_jabatan
            ):
                frappe.msgprint(
                    _("Biaya Jabatan percentage must be between {0}% and {1}%").format(
                        min_biaya_jabatan, max_biaya_jabatan
                    ),
                    indicator="orange",
                )

    @safe_execute(log_exception=True)
    def _validate_bpjs_settings(self) -> None:
        """
        Validate BPJS-related settings.

        Uses central validation helpers and ensures BPJS percentages
        are within valid ranges defined in configuration.
        """
        # Only validate if the tables exist
        if not frappe.db.table_exists("Payroll Indonesia Settings"):
            logger.warning("Payroll Indonesia Settings table does not exist yet")
            return

        # Get config limits
        config = get_live_config()
        bpjs_limits = config.get("bpjs", {}).get("limits", {})

        # BPJS Kesehatan limits
        min_kesehatan_employee = bpjs_limits.get("min_kesehatan_employee_percent", 0)
        max_kesehatan_employee = bpjs_limits.get("max_kesehatan_employee_percent", 5)
        min_kesehatan_employer = bpjs_limits.get("min_kesehatan_employer_percent", 0)
        max_kesehatan_employer = bpjs_limits.get("max_kesehatan_employer_percent", 10)

        # Validate BPJS Kesehatan percentages
        if hasattr(self, "kesehatan_employee_percent"):
            if (
                self.kesehatan_employee_percent < min_kesehatan_employee
                or self.kesehatan_employee_percent > max_kesehatan_employee
            ):
                frappe.msgprint(
                    _("BPJS Kesehatan employee percentage must be between {0}% and {1}%").format(
                        min_kesehatan_employee, max_kesehatan_employee
                    ),
                    indicator="orange",
                )

        if hasattr(self, "kesehatan_employer_percent"):
            if (
                self.kesehatan_employer_percent < min_kesehatan_employer
                or self.kesehatan_employer_percent > max_kesehatan_employer
            ):
                frappe.msgprint(
                    _("BPJS Kesehatan employer percentage must be between {0}% and {1}%").format(
                        min_kesehatan_employer, max_kesehatan_employer
                    ),
                    indicator="orange",
                )

        # JHT limits
        min_jht_employee = bpjs_limits.get("min_jht_employee_percent", 0)
        max_jht_employee = bpjs_limits.get("max_jht_employee_percent", 5)
        min_jht_employer = bpjs_limits.get("min_jht_employer_percent", 0)
        max_jht_employer = bpjs_limits.get("max_jht_employer_percent", 10)

        # Validate JHT percentages
        if hasattr(self, "jht_employee_percent"):
            if (
                self.jht_employee_percent < min_jht_employee
                or self.jht_employee_percent > max_jht_employee
            ):
                frappe.msgprint(
                    _("BPJS JHT employee percentage must be between {0}% and {1}%").format(
                        min_jht_employee, max_jht_employee
                    ),
                    indicator="orange",
                )

        if hasattr(self, "jht_employer_percent"):
            if (
                self.jht_employer_percent < min_jht_employer
                or self.jht_employer_percent > max_jht_employer
            ):
                frappe.msgprint(
                    _("BPJS JHT employer percentage must be between {0}% and {1}%").format(
                        min_jht_employer, max_jht_employer
                    ),
                    indicator="orange",
                )

        # Validate BPJS components existence using central validation
        if hasattr(self, "company") and self.company:
            # Only check if Salary Component table exists
            if frappe.db.table_exists("Salary Component"):
                try:
                    validate_bpjs_components(self.company)
                except Exception as e:
                    logger.warning(f"BPJS component validation warning: {str(e)}")
                    # Show as warning, not error
                    frappe.msgprint(str(e), indicator="orange")
            else:
                logger.warning("Salary Component table does not exist yet")

    @safe_execute(log_exception=True)
    def _validate_json_fields(self) -> None:
        """
        Validate JSON fields have valid content.

        Ensures all JSON fields contain valid JSON data.
        """
        json_fields = [
            "bpjs_account_mapping_json",
            "expense_accounts_json",
            "payable_accounts_json",
            "parent_accounts_json",
            "ter_rate_ter_a_json",
            "ter_rate_ter_b_json",
            "ter_rate_ter_c_json",
        ]

        for field in json_fields:
            if hasattr(self, field) and self.get(field):
                try:
                    json.loads(self.get(field))
                except json.JSONDecodeError:
                    frappe.msgprint(
                        _("Invalid JSON format in field {0}").format(frappe.unscrub(field)),
                        indicator="red",
                    )

    @safe_execute(log_exception=True)
    def _sync_to_related_doctypes(self) -> None:
        """
        Sync settings to related DocTypes.

        Updates BPJS Settings and PPh 21 Settings with relevant values from this DocType.
        """
        # Sync to BPJS Settings
        self._sync_to_bpjs_settings()

        # Sync to PPh 21 Settings
        self._sync_to_pph_settings()

        logger.info("Synced settings to related DocTypes")

    @safe_execute(log_exception=True)
    def _sync_to_bpjs_settings(self) -> None:
        """
        Sync settings to BPJS Settings DocType.

        Internal helper for sync_to_related_doctypes method.
        """
        # First check if DocType and table exist
        if not frappe.db.table_exists("BPJS Settings"):
            logger.info("BPJS Settings table does not exist yet, skipping sync")
            return

        if frappe.db.exists("DocType", "BPJS Settings") and frappe.db.exists(
            "BPJS Settings", "BPJS Settings"
        ):
            bpjs_settings = frappe.get_doc("BPJS Settings", "BPJS Settings")
            bpjs_fields = [
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
            for field in bpjs_fields:
                if (
                    hasattr(bpjs_settings, field)
                    and hasattr(self, field)
                    and bpjs_settings.get(field) != self.get(field)
                ):
                    bpjs_settings.set(field, self.get(field))
                    needs_update = True

            if needs_update:
                bpjs_settings.flags.ignore_validate = True
                bpjs_settings.flags.ignore_permissions = True
                bpjs_settings.save()
                logger.info("Updated BPJS Settings from Payroll Indonesia Settings")
                frappe.msgprint(
                    _("BPJS Settings updated from Payroll Indonesia Settings"),
                    indicator="green",
                )

    @safe_execute(log_exception=True)
    def _sync_to_pph_settings(self) -> None:
        """
        Sync settings to PPh 21 Settings DocType.

        Internal helper for sync_to_related_doctypes method.
        """
        # First check if DocType and table exist
        if not frappe.db.table_exists("PPh 21 Settings"):
            logger.info("PPh 21 Settings table does not exist yet, skipping sync")
            return

        if frappe.db.exists("DocType", "PPh 21 Settings") and frappe.db.exists(
            "PPh 21 Settings", "PPh 21 Settings"
        ):
            pph_settings = frappe.get_doc("PPh 21 Settings", "PPh 21 Settings")

            # Update calculation method and TER usage flag
            needs_update = False

            if (
                hasattr(pph_settings, "calculation_method")
                and pph_settings.calculation_method != self.tax_calculation_method
            ):
                pph_settings.calculation_method = self.tax_calculation_method
                needs_update = True

            # Sync the use_ter field if it exists in PPh 21 Settings
            if hasattr(pph_settings, "use_ter") and pph_settings.use_ter != self.use_ter:
                pph_settings.use_ter = self.use_ter
                needs_update = True

            if needs_update:
                pph_settings.flags.ignore_validate = True
                pph_settings.flags.ignore_permissions = True
                pph_settings.save()
                logger.info("Updated PPh 21 Settings from Payroll Indonesia Settings")
                frappe.msgprint(
                    _("PPh 21 Settings updated from Payroll Indonesia Settings"),
                    indicator="green",
                )

    @safe_execute(log_exception=True)
    def _sync_to_defaults_json(self) -> None:
        """
        Sync current settings to defaults.json.

        This allows configuration to be tracked in version control.
        Only runs if explicitly enabled in config.
        """
        try:
            import os
            from pathlib import Path

            # Get app path
            app_path = frappe.get_app_path("payroll_indonesia")
            config_path = Path(app_path) / "config"
            defaults_file = config_path / "defaults.json"

            # Ensure config directory exists
            if not config_path.exists():
                os.makedirs(config_path)

            # Read existing defaults if file exists
            if defaults_file.exists():
                with open(defaults_file, "r") as f:
                    defaults = json.load(f)
            else:
                defaults = {}

            # Update BPJS settings
            if "bpjs" not in defaults:
                defaults["bpjs"] = {}

            bpjs_fields = {
                "kesehatan_employee_percent": "kesehatan_employee_percent",
                "kesehatan_employer_percent": "kesehatan_employer_percent",
                "kesehatan_max_salary": "kesehatan_max_salary",
                "jht_employee_percent": "jht_employee_percent",
                "jht_employer_percent": "jht_employer_percent",
                "jp_employee_percent": "jp_employee_percent",
                "jp_employer_percent": "jp_employer_percent",
                "jp_max_salary": "jp_max_salary",
                "jkk_percent": "jkk_percent",
                "jkm_percent": "jkm_percent",
            }

            for config_field, doc_field in bpjs_fields.items():
                if hasattr(self, doc_field):
                    defaults["bpjs"][config_field] = flt(self.get(doc_field))

            # Update tax settings
            if "tax" not in defaults:
                defaults["tax"] = {}

            defaults["tax"]["tax_calculation_method"] = self.tax_calculation_method
            defaults["tax"]["use_ter"] = cint(self.use_ter)

            if hasattr(self, "biaya_jabatan_percent"):
                defaults["tax"]["biaya_jabatan_percent"] = flt(self.biaya_jabatan_percent)

            if hasattr(self, "biaya_jabatan_max"):
                defaults["tax"]["biaya_jabatan_max"] = flt(self.biaya_jabatan_max)

            # Update PTKP values
            if hasattr(self, "ptkp_table") and self.ptkp_table:
                defaults["ptkp"] = {}
                for row in self.ptkp_table:
                    defaults["ptkp"][row.status_pajak] = flt(row.ptkp_amount)

            # Update PTKP to TER mapping
            if hasattr(self, "ptkp_ter_mapping_table") and self.ptkp_ter_mapping_table:
                defaults["ptkp_to_ter_mapping"] = {}
                for row in self.ptkp_ter_mapping_table:
                    defaults["ptkp_to_ter_mapping"][row.ptkp_status] = row.ter_category

            # Update tax brackets
            if hasattr(self, "tax_brackets_table") and self.tax_brackets_table:
                defaults["tax_brackets"] = []
                for row in self.tax_brackets_table:
                    defaults["tax_brackets"].append(
                        {
                            "income_from": flt(row.income_from),
                            "income_to": flt(row.income_to),
                            "tax_rate": flt(row.tax_rate),
                        }
                    )

            # Update employee types
            if hasattr(self, "tipe_karyawan") and self.tipe_karyawan:
                defaults["tipe_karyawan"] = []
                for row in self.tipe_karyawan:
                    defaults["tipe_karyawan"].append(row.tipe_karyawan)

            # Update defaults.json with a timestamp
            defaults["app_info"] = {
                "version": self.app_version if hasattr(self, "app_version") else "1.0.0",
                "last_updated": str(now()),
                "updated_by": frappe.session.user,
            }

            # Write updated defaults to file
            with open(defaults_file, "w") as f:
                json.dump(defaults, f, indent=2)

            logger.info(f"Synced settings to defaults.json by {frappe.session.user}")
            frappe.msgprint(_("Settings synced to defaults.json"), indicator="green")

        except Exception as e:
            logger.error(f"Error syncing settings to defaults.json: {str(e)}")
            frappe.log_error(
                f"Error syncing settings to defaults.json: {str(e)}", "Settings Sync Error"
            )

    @safe_execute(log_exception=True)
    def _populate_default_values(self) -> None:
        """
        Populate default values from configuration if fields are empty.

        Uses central configuration to populate child tables and settings fields.
        """
        # Get configuration
        config = get_config()
        defaults_loaded = False

        # Delegate to specific population methods
        defaults_loaded |= self._populate_ptkp_values(config)
        defaults_loaded |= self._populate_tax_brackets(config)
        defaults_loaded |= self._populate_employee_types(config)
        defaults_loaded |= self._populate_ptkp_ter_mapping(config)
        defaults_loaded |= self._populate_ter_rates(config)

        # Apply any basic field defaults from config
        defaults_loaded |= self._populate_basic_settings(config)

        # If defaults were loaded, update the database
        if defaults_loaded:
            try:
                self.db_update()
                logger.info("Updated database with default values")
                frappe.msgprint(_("Default values loaded from configuration"), indicator="green")
            except Exception as e:
                logger.error(f"Error updating database with defaults: {str(e)}")
                frappe.log_error(
                    f"Error updating database with defaults: {str(e)}", "Settings Error"
                )

    def _populate_ptkp_values(self, config: Dict[str, Any]) -> bool:
        """
        Populate PTKP values from config if not already defined.

        Args:
            config: Configuration dictionary

        Returns:
            bool: True if values were populated, False otherwise
        """
        # Check if values need to be populated
        if not hasattr(self, "ptkp_table") or self.ptkp_table:
            return False

        # Extract PTKP data from config
        ptkp_values = config.get("ptkp", {})
        if not ptkp_values:
            logger.info("No PTKP values found in configuration")
            return False

        # Clear existing rows if any
        self.set("ptkp_table", [])

        # Add values from config
        for status_code, amount in ptkp_values.items():
            self.append("ptkp_table", {"status_pajak": status_code, "ptkp_amount": flt(amount)})

        logger.info(f"Populated {len(ptkp_values)} PTKP values from configuration")
        return True

    def _populate_tax_brackets(self, config: Dict[str, Any]) -> bool:
        """
        Populate tax brackets from config if not already defined.

        Args:
            config: Configuration dictionary

        Returns:
            bool: True if values were populated, False otherwise
        """
        # Check if values need to be populated
        if not hasattr(self, "tax_brackets_table") or self.tax_brackets_table:
            return False

        # Extract tax brackets from config
        tax_brackets = config.get("tax_brackets", [])
        if not tax_brackets:
            logger.info("No tax brackets found in configuration")
            return False

        # Clear existing rows if any
        self.set("tax_brackets_table", [])

        # Add brackets from config
        for bracket in tax_brackets:
            self.append(
                "tax_brackets_table",
                {
                    "income_from": flt(bracket.get("income_from", 0)),
                    "income_to": flt(bracket.get("income_to", 0)),
                    "tax_rate": flt(bracket.get("tax_rate", 0)),
                },
            )

        logger.info(f"Populated {len(tax_brackets)} tax brackets from configuration")
        return True

    def _populate_employee_types(self, config: Dict[str, Any]) -> bool:
        """
        Populate employee types from config if not already defined.

        Args:
            config: Configuration dictionary

        Returns:
            bool: True if values were populated, False otherwise
        """
        # Check if values need to be populated
        if not hasattr(self, "tipe_karyawan") or self.tipe_karyawan:
            return False

        # Extract employee types from config
        tipe_karyawan = config.get("tipe_karyawan", [])
        if not tipe_karyawan:
            logger.info("No employee types found in configuration")
            return False

        # Clear existing rows if any
        self.set("tipe_karyawan", [])

        # Add types from config
        for tipe in tipe_karyawan:
            self.append("tipe_karyawan", {"tipe_karyawan": tipe})

        logger.info(f"Populated {len(tipe_karyawan)} employee types from configuration")
        return True

    def _populate_ptkp_ter_mapping(self, config: Dict[str, Any]) -> bool:
        """
        Populate PTKP to TER mapping from config if not already defined.

        Args:
            config: Configuration dictionary

        Returns:
            bool: True if values were populated, False otherwise
        """
        # Check if values need to be populated
        if not hasattr(self, "ptkp_ter_mapping_table") or self.ptkp_ter_mapping_table:
            return False

        # Extract mapping from config
        mapping_data = config.get("ptkp_to_ter_mapping", {})
        if not mapping_data:
            logger.info("No PTKP to TER mapping found in configuration")
            return False

        # Clear existing rows if any
        self.set("ptkp_ter_mapping_table", [])

        # Add mapping from config
        for ptkp_code, ter_category in mapping_data.items():
            self.append(
                "ptkp_ter_mapping_table", {"ptkp_status": ptkp_code, "ter_category": ter_category}
            )

        logger.info(f"Populated {len(mapping_data)} PTKP to TER mappings from configuration")
        return True

    def _populate_ter_rates(self, config: Dict[str, Any]) -> bool:
        """
        Populate TER rates from config if not already defined.

        Args:
            config: Configuration dictionary

        Returns:
            bool: True if values were populated, False otherwise
        """
        # Extract TER rates from config
        ter_rates = config.get("ter_rates", {})
        if not ter_rates:
            logger.info("No TER rates found in configuration")
            return False

        updated = False

        # Store TER A rates in JSON field if available
        if (
            "TER A" in ter_rates
            and hasattr(self, "ter_rate_ter_a_json")
            and not self.ter_rate_ter_a_json
        ):
            self.ter_rate_ter_a_json = json.dumps(ter_rates["TER A"])
            updated = True

        # Store TER B rates in JSON field if available
        if (
            "TER B" in ter_rates
            and hasattr(self, "ter_rate_ter_b_json")
            and not self.ter_rate_ter_b_json
        ):
            self.ter_rate_ter_b_json = json.dumps(ter_rates["TER B"])
            updated = True

        # Store TER C rates in JSON field if available
        if (
            "TER C" in ter_rates
            and hasattr(self, "ter_rate_ter_c_json")
            and not self.ter_rate_ter_c_json
        ):
            self.ter_rate_ter_c_json = json.dumps(ter_rates["TER C"])
            updated = True

        # If there's a table for TER rates, populate it
        if hasattr(self, "ter_rates_table") and not self.ter_rates_table:
            # Process each TER category
            for category_name, rates in ter_rates.items():
                # Skip metadata entry
                if category_name == "metadata":
                    continue

                # Add each rate in the category
                for rate in rates:
                    self.append(
                        "ter_rates_table",
                        {
                            "category": category_name,
                            "income_from": flt(rate.get("income_from", 0)),
                            "income_to": flt(rate.get("income_to", 0)),
                            "rate": flt(rate.get("rate", 0)),
                            "is_highest_bracket": cint(rate.get("is_highest_bracket", 0)),
                        },
                    )

            updated = True

        # Set TER metadata if available
        metadata = ter_rates.get("metadata", {})
        if metadata:
            if hasattr(self, "ter_regulation_ref") and not self.ter_regulation_ref:
                self.ter_regulation_ref = metadata.get("regulation_ref", "")
                updated = True

            if hasattr(self, "ter_effective_date") and not self.ter_effective_date:
                self.ter_effective_date = metadata.get("effective_date", "")
                updated = True

            if hasattr(self, "ter_description") and not self.ter_description:
                self.ter_description = metadata.get("description", "")
                updated = True

            if hasattr(self, "ter_default_category") and not self.ter_default_category:
                self.ter_default_category = metadata.get("default_category", "TER A")
                updated = True

            if hasattr(self, "ter_fallback_rate") and not self.ter_fallback_rate:
                self.ter_fallback_rate = flt(metadata.get("fallback_rate", 5.0))
                updated = True

        if updated:
            logger.info("Populated TER rates from configuration")

        return updated

    def _populate_basic_settings(self, config: Dict[str, Any]) -> bool:
        """
        Populate basic setting fields from configuration.

        Args:
            config: Configuration dictionary

        Returns:
            bool: True if values were populated, False otherwise
        """
        updated = False

        # BPJS settings
        bpjs_config = config.get("bpjs", {})
        if bpjs_config:
            bpjs_fields = [
                ("kesehatan_employee_percent", 1.0),
                ("kesehatan_employer_percent", 4.0),
                ("kesehatan_max_salary", 12000000.0),
                ("jht_employee_percent", 2.0),
                ("jht_employer_percent", 3.7),
                ("jp_employee_percent", 1.0),
                ("jp_employer_percent", 2.0),
                ("jp_max_salary", 9077600.0),
                ("jkk_percent", 0.24),
                ("jkm_percent", 0.3),
            ]

            for field_name, default_value in bpjs_fields:
                if hasattr(self, field_name) and not self.get(field_name):
                    setattr(self, field_name, flt(bpjs_config.get(field_name, default_value)))
                    updated = True

        # Tax settings
        tax_config = config.get("tax", {})
        if tax_config:
            if hasattr(self, "tax_calculation_method") and not self.tax_calculation_method:
                self.tax_calculation_method = tax_config.get("tax_calculation_method", "TER")
                updated = True

            if hasattr(self, "use_ter") and not self.use_ter:
                self.use_ter = cint(tax_config.get("use_ter", 1))
                updated = True

            if hasattr(self, "biaya_jabatan_percent") and not self.biaya_jabatan_percent:
                self.biaya_jabatan_percent = flt(tax_config.get("biaya_jabatan_percent", 5.0))
                updated = True

            if hasattr(self, "biaya_jabatan_max") and not self.biaya_jabatan_max:
                self.biaya_jabatan_max = flt(tax_config.get("biaya_jabatan_max", 500000.0))
                updated = True

            if hasattr(self, "npwp_mandatory") and not self.npwp_mandatory:
                self.npwp_mandatory = cint(tax_config.get("npwp_mandatory", 0))
                updated = True

        # Default settings
        defaults = config.get("defaults", {})
        if defaults:
            if hasattr(self, "default_currency") and not self.default_currency:
                self.default_currency = defaults.get("currency", "IDR")
                updated = True

            if (
                hasattr(self, "attendance_based_on_timesheet")
                and not self.attendance_based_on_timesheet
            ):
                self.attendance_based_on_timesheet = cint(
                    defaults.get("attendance_based_on_timesheet", 0)
                )
                updated = True

            if hasattr(self, "payroll_frequency") and not self.payroll_frequency:
                self.payroll_frequency = defaults.get("payroll_frequency", "Monthly")
                updated = True

            if hasattr(self, "salary_slip_based_on") and not self.salary_slip_based_on:
                self.salary_slip_based_on = defaults.get("salary_slip_based_on", "Leave Policy")
                updated = True

            if hasattr(self, "max_working_days_per_month") and not self.max_working_days_per_month:
                self.max_working_days_per_month = cint(
                    defaults.get("max_working_days_per_month", 22)
                )
                updated = True

            if (
                hasattr(self, "include_holidays_in_total_working_days")
                and not self.include_holidays_in_total_working_days
            ):
                self.include_holidays_in_total_working_days = cint(
                    defaults.get("include_holidays_in_total_working_days", 0)
                )
                updated = True

            if hasattr(self, "working_hours_per_day") and not self.working_hours_per_day:
                self.working_hours_per_day = flt(defaults.get("working_hours_per_day", 8))
                updated = True

        # Salary structure settings
        struktur_gaji = config.get("struktur_gaji", {})
        if struktur_gaji:
            if hasattr(self, "basic_salary_percent") and not self.basic_salary_percent:
                self.basic_salary_percent = flt(struktur_gaji.get("basic_salary_percent", 75))
                updated = True

            if hasattr(self, "meal_allowance_default") and not self.meal_allowance_default:
                self.meal_allowance_default = flt(struktur_gaji.get("meal_allowance", 750000.0))
                updated = True

            if (
                hasattr(self, "transport_allowance_default")
                and not self.transport_allowance_default
            ):
                self.transport_allowance_default = flt(
                    struktur_gaji.get("transport_allowance", 900000.0)
                )
                updated = True

            if hasattr(self, "umr_default") and not self.umr_default:
                self.umr_default = flt(struktur_gaji.get("umr_default", 4900000.0))
                updated = True

            if hasattr(self, "position_allowance_percent") and not self.position_allowance_percent:
                self.position_allowance_percent = flt(
                    struktur_gaji.get("position_allowance_percent", 7.5)
                )
                updated = True

            if hasattr(self, "working_days_default") and not self.working_days_default:
                self.working_days_default = cint(struktur_gaji.get("hari_kerja_default", 22))
                updated = True

        if updated:
            logger.info("Populated basic settings from configuration")

        return updated

    # Public utility methods

    def get_ptkp_values_dict(self) -> Dict[str, float]:
        """
        Return PTKP values as a dictionary.

        Returns:
            Dict[str, float]: Dictionary mapping PTKP status codes to amounts
        """
        ptkp_dict: Dict[str, float] = {}
        if hasattr(self, "ptkp_table") and self.ptkp_table:
            for row in self.ptkp_table:
                ptkp_dict[row.status_pajak] = flt(row.ptkp_amount)
        return ptkp_dict

    def get_ptkp_ter_mapping_dict(self) -> Dict[str, str]:
        """
        Return PTKP to TER mapping as a dictionary.

        Returns:
            Dict[str, str]: Dictionary mapping PTKP status codes to TER categories
        """
        mapping_dict: Dict[str, str] = {}
        if hasattr(self, "ptkp_ter_mapping_table") and self.ptkp_ter_mapping_table:
            for row in self.ptkp_ter_mapping_table:
                mapping_dict[row.ptkp_status] = row.ter_category
        return mapping_dict

    def get_tax_brackets_list(self) -> List[Dict[str, float]]:
        """
        Return tax brackets as a list of dictionaries.

        Returns:
            List[Dict[str, float]]: List of tax bracket configurations
        """
        brackets: List[Dict[str, float]] = []
        if hasattr(self, "tax_brackets_table") and self.tax_brackets_table:
            for row in self.tax_brackets_table:
                brackets.append(
                    {
                        "income_from": flt(row.income_from),
                        "income_to": flt(row.income_to),
                        "tax_rate": flt(row.tax_rate),
                    }
                )
        return brackets

    def get_tipe_karyawan_list(self) -> List[str]:
        """
        Return employee types as a list.

        Returns:
            List[str]: List of employee type names
        """
        types: List[str] = []
        if hasattr(self, "tipe_karyawan") and self.tipe_karyawan:
            for row in self.tipe_karyawan:
                types.append(row.tipe_karyawan)

        # If empty, get from configuration
        if not types:
            config = get_config()
            types = config.get("tipe_karyawan", [])

        return types
