"""
setup_module.py – consolidated setup routines for Payroll Indonesia.
Provides centralized setup functions used during installation and updates.
"""

import logging
from typing import Dict, Any, Optional, List, cast

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from payroll_indonesia.config.config import get_live_config
from payroll_indonesia.frappe_helpers import safe_execute, doc_exists
from payroll_indonesia.setup.settings_migration import migrate_all_settings

# Configure logger
logger = logging.getLogger(__name__)


def main(config: Optional[Dict[str, Any]] = None) -> bool:
    """
    Main entry point for Payroll Indonesia setup routines.

    Args:
        config: Configuration dictionary (optional, will use get_live_config if None)

    Returns:
        bool: Success status of setup operations
    """
    if config is None:
        config = get_live_config()

    logger.info(_("Starting Payroll Indonesia setup"))

    # Run setup functions in sequence
    results = [
        setup_payroll_settings(config),
        setup_salary_components(config),
        setup_property_setters(config),
        setup_bpjs_mappings_for_companies(config),
        migrate_config_to_settings(config),
    ]

    # Check if all setup functions succeeded
    success = all(results)

    if success:
        logger.info(_("Payroll Indonesia setup completed successfully"))
    else:
        logger.warning(_("Payroll Indonesia setup completed with warnings"))

    return success


@safe_execute(default_value=False, log_exception=True)
def setup_payroll_settings(config: Dict[str, Any]) -> bool:
    """
    Ensure Payroll Indonesia Settings document exists.

    Args:
        config: Configuration dictionary

    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(_("Setting up Payroll Indonesia Settings"))

    # Check if DocType exists
    if not frappe.db.table_exists("Payroll Indonesia Settings"):
        logger.warning(_("Payroll Indonesia Settings DocType does not exist"))
        return False

    settings_name = "Payroll Indonesia Settings"

    if not doc_exists(settings_name, settings_name):
        logger.info(_("Creating Payroll Indonesia Settings"))

        settings = frappe.new_doc(settings_name)
        settings.document_name = settings_name
        settings.enabled = 1
        settings.auto_create_salary_structure = 1

        # Set defaults from config
        defaults = config.get("defaults", {})
        if defaults:
            settings.default_currency = defaults.get("currency", "IDR")
            settings.max_working_days_per_month = defaults.get("max_working_days_per_month", 22)
            settings.working_hours_per_day = flt(defaults.get("working_hours_per_day", 8))

        # Save with ignore_permissions
        settings.flags.ignore_permissions = True
        settings.insert(ignore_permissions=True)
        frappe.db.commit()

        logger.info(_("Successfully created Payroll Indonesia Settings"))
    else:
        logger.info(_("Payroll Indonesia Settings already exists"))

    return True


@safe_execute(default_value=False, log_exception=True)
def setup_salary_components(config: Dict[str, Any]) -> bool:
    """
    Set up required salary components from configuration.

    Args:
        config: Configuration dictionary

    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(_("Setting up salary components"))

    # Check if DocType exists
    if not frappe.db.table_exists("Salary Component"):
        logger.warning(_("Salary Component DocType does not exist"))
        return False

    components_config = config.get("salary_components", {})

    if not components_config:
        logger.warning(_("No salary components found in configuration"))
        return True

    created_count = 0
    skipped_count = 0

    # Process earnings
    earnings = components_config.get("earnings", [])
    for comp in earnings:
        if not doc_exists("Salary Component", comp.get("name")):
            doc = frappe.new_doc("Salary Component")
            doc.salary_component = comp.get("name")
            doc.salary_component_abbr = comp.get("abbr")
            doc.type = "Earning"

            if comp.get("is_tax_applicable"):
                doc.is_tax_applicable = 1

            doc.insert()
            created_count += 1
            logger.info(_("Created earning component: {0}").format(comp.get("name")))
        else:
            skipped_count += 1

    # Process deductions
    deductions = components_config.get("deductions", [])
    for comp in deductions:
        if not doc_exists("Salary Component", comp.get("name")):
            doc = frappe.new_doc("Salary Component")
            doc.salary_component = comp.get("name")
            doc.salary_component_abbr = comp.get("abbr")
            doc.type = "Deduction"

            # Add optional fields
            if comp.get("statistical_component"):
                doc.statistical_component = 1

            if comp.get("variable_based_on_taxable_salary"):
                doc.variable_based_on_taxable_salary = 1

            doc.insert()
            created_count += 1
            logger.info(_("Created deduction component: {0}").format(comp.get("name")))
        else:
            skipped_count += 1

    frappe.db.commit()
    logger.info(
        _("Salary components setup completed: created={0}, skipped={1}").format(
            created_count, skipped_count
        )
    )

    return True


@safe_execute(default_value=False, log_exception=True)
def setup_property_setters(config: Dict[str, Any]) -> bool:
    """
    Set up property setters for customizing form behavior.

    Args:
        config: Configuration dictionary

    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(_("Setting up property setters"))

    # Check if DocType exists
    if not frappe.db.table_exists("Property Setter"):
        logger.warning(_("Property Setter DocType does not exist"))
        return False

    property_setters = [
        {
            "doctype": "Salary Structure",
            "property": "max_benefits",
            "value": "20",
            "property_type": "Int",
        },
        {
            "doctype": "Employee",
            "property": "paidup_ptkp",
            "value": "1",
            "property_type": "Check",
        },
        {
            "doctype": "Salary Slip",
            "property": "show_jht_in_earnings",
            "value": "0",
            "property_type": "Check",
        },
    ]

    created_count = 0
    skipped_count = 0

    for ps in property_setters:
        ps_name = f"{ps['doctype']}-{ps['property']}"

        if not doc_exists("Property Setter", ps_name):
            doc = frappe.new_doc("Property Setter")
            doc.doc_type = ps["doctype"]
            doc.property = ps["property"]
            doc.value = ps["value"]
            doc.property_type = ps["property_type"]
            doc.doctype_or_field = "DocType"
            doc.insert()
            created_count += 1
            logger.info(_("Created property setter: {0}").format(ps_name))
        else:
            skipped_count += 1

    frappe.db.commit()
    logger.info(
        _("Property setters setup completed: created={0}, skipped={1}").format(
            created_count, skipped_count
        )
    )

    return True


@safe_execute(default_value=False, log_exception=True)
def setup_bpjs_mappings_for_companies(config: Dict[str, Any]) -> bool:
    """
    Create BPJS Account Mapping for all companies if they don't exist.

    Args:
        config: Configuration dictionary

    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(_("Setting up BPJS Account Mappings for companies"))

    # Check if DocType exists
    if not frappe.db.table_exists("BPJS Account Mapping"):
        logger.warning(_("BPJS Account Mapping DocType does not exist"))
        return False

    if not frappe.db.table_exists("Company"):
        logger.warning(_("Company DocType does not exist"))
        return False

    companies = frappe.get_all("Company", filters={"is_group": 0, "disabled": 0}, pluck="name")

    if not companies:
        logger.warning(_("No active companies found"))
        return True

    created_count = 0
    skipped_count = 0

    for company in companies:
        if doc_exists("BPJS Account Mapping", {"company": company}):
            logger.info(_("BPJS Account Mapping exists for company: {0}").format(company))
            skipped_count += 1
        else:
            result = create_bpjs_mapping_for_company(company, config)
            if result:
                created_count += 1

    logger.info(
        _("BPJS Account Mapping setup completed: created={0}, skipped={1}").format(
            created_count, skipped_count
        )
    )

    return True


@safe_execute(default_value=None, log_exception=True)
def create_bpjs_mapping_for_company(
    company: str, config: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Create a BPJS Account Mapping for a specific company.

    Args:
        company: Company name
        config: Configuration dictionary

    Returns:
        Optional[Dict[str, Any]]: Created mapping or None if failed
    """
    logger.info(_("Creating BPJS Account Mapping for company: {0}").format(company))

    mapping = frappe.new_doc("BPJS Account Mapping")
    mapping.company = company
    mapping.mapping_name = f"BPJS Mapping - {company}"

    # Set default accounts from config if available
    bpjs_config = config.get("bpjs_settings", {})
    if bpjs_config:
        account_fields = bpjs_config.get("account_fields", [])
        for field in account_fields:
            setattr(mapping, field, "")

    # Set blank accounts
    mapping.bpjs_kesehatan_employee_account = ""
    mapping.bpjs_kesehatan_employer_account = ""
    mapping.bpjs_ketenagakerjaan_jht_employee_account = ""
    mapping.bpjs_ketenagakerjaan_jht_employer_account = ""
    mapping.bpjs_ketenagakerjaan_jp_employee_account = ""
    mapping.bpjs_ketenagakerjaan_jp_employer_account = ""
    mapping.bpjs_ketenagakerjaan_jkk_account = ""
    mapping.bpjs_ketenagakerjaan_jkm_account = ""

    # Default payable accounts
    mapping.bpjs_kesehatan_payable_account = ""
    mapping.bpjs_ketenagakerjaan_payable_account = ""

    # Default cost center
    mapping.default_cost_center = ""

    # Insert with ignore_permissions
    mapping.flags.ignore_permissions = True
    mapping.insert(ignore_permissions=True)

    logger.info(_("Created BPJS Account Mapping for company: {0}").format(company))

    return mapping


@safe_execute(default_value=False, log_exception=True)
def migrate_config_to_settings(config: Dict[str, Any]) -> bool:
    """
    Migrate configuration from defaults.json to the Payroll Indonesia Settings DocType.
    
    This function delegates migration of different sections to specialized helpers
    in the settings_migration module.

    Args:
        config: Configuration dictionary

    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(_("Starting migration of configuration to Payroll Indonesia Settings"))
    
    # Check if DocType exists
    if not frappe.db.table_exists("Payroll Indonesia Settings"):
        logger.warning(_("Payroll Indonesia Settings DocType does not exist"))
        return False
    
    if not config:
        logger.warning(_("No configuration to migrate"))
        return False

    try:
        # Get or create settings document
        settings_name = "Payroll Indonesia Settings"
        if doc_exists(settings_name, settings_name):
            settings = frappe.get_doc(settings_name, settings_name)
        else:
            settings = frappe.new_doc(settings_name)
            settings.document_name = settings_name
        
        # Perform the migration
        results = migrate_all_settings(settings, config)
        
        # Save the document
        settings.flags.ignore_permissions = True
        
        if settings.is_new():
            settings.insert(ignore_permissions=True)
            logger.info(_("Created new Payroll Indonesia Settings with migrated configuration"))
        else:
            settings.save(ignore_permissions=True)
            logger.info(_("Updated existing Payroll Indonesia Settings with migrated configuration"))
        
        frappe.db.commit()
        
        # Log migration results
        succeeded = sum(1 for result in results.values() if result)
        failed = len(results) - succeeded
        
        logger.info(
            _("Configuration migration completed: {0}/{1} sections migrated successfully")
            .format(succeeded, len(results))
        )
        
        if failed > 0:
            logger.warning(
                _("Failed to migrate {0} sections")
                .format(failed)
            )
            
            # Log the failed sections
            for section, success in results.items():
                if not success:
                    logger.warning(_("Failed to migrate section: {0}").format(section))
        
        return succeeded > 0
        
    except Exception as e:
        logger.error(_("Error migrating configuration to settings: {0}").format(str(e)))
        frappe.log_error(
            _("Error migrating configuration to settings: {0}\n{1}")
            .format(str(e), frappe.get_traceback()),
            "Configuration Migration Error"
        )
        return False
