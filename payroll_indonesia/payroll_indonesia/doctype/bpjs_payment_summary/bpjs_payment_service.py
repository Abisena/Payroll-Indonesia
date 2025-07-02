# -*- coding: utf-8 -*-
# Copyright (c) 2025, PT. Innovasi Terbaik Bangsa and contributors
# For license information, please see license.txt
# Last modified: 2025-07-02 15:39:47 by dannyaudian

"""
Service layer for BPJS Payment Summary document.

This module provides the PaymentSummaryService class that handles the business logic
for creating payment entries and journal entries from BPJS Payment Summary documents.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from payroll_indonesia.payroll_indonesia.doctype.bpjs_account_mapping.bpjs_account_mapping import (
    get_mapping_for_company,
)

from .bpjs_payment_utils import debug_log

# Configure logger
logger = logging.getLogger(__name__)


class PaymentSummaryService:
    """
    Service class for BPJS Payment Summary operations.
    
    This class handles the business logic for creating payment entries and
    journal entries from BPJS Payment Summary documents.
    """

    def __init__(self, doc: Any) -> None:
        """
        Initialize PaymentSummaryService.
        
        Args:
            doc: BPJS Payment Summary document instance
        """
        self.doc = doc
        self._company_abbr = getattr(doc, "_company_abbr", None) or frappe.get_cached_value(
            "Company", doc.company, "abbr"
        )
        
    def set_account_details(self) -> None:
        """
        Set account details from BPJS Settings and Account Mapping.
        
        Populates account_details child table based on company settings and mappings.
        
        Raises:
            frappe.DoesNotExistError: If required mappings don't exist.
        """
        # Clear existing account_details
        self.doc.account_details = []
        
        # Find BPJS Account Mapping for this company
        account_mapping = None
        try:
            account_mapping = get_mapping_for_company(self.doc.company)
        except frappe.DoesNotExistError:
            debug_log(
                f"No BPJS Account Mapping found for company {self.doc.company}",
                "BPJS Payment Summary"
            )
            
        if account_mapping:
            # Use company-specific mapping
            # Calculate totals for each BPJS type from employee_details
            bpjs_totals = self.doc.calculate_bpjs_type_totals()
            
            # Add account details using mapping
            account_types = ["Kesehatan", "JHT", "JP", "JKK", "JKM"]
            
            # Batch collect all account names to check
            account_names = []
            for bpjs_type in account_types:
                employer_credit_field = f"{bpjs_type.lower()}_employer_credit_account"
                if (
                    employer_credit_field in account_mapping
                    and account_mapping[employer_credit_field]
                ):
                    account_names.append(account_mapping[employer_credit_field])
                    
            # Bulk check account existence
            if account_names:
                existing_accounts = frappe.db.get_all(
                    "Account", filters={"name": ["in", account_names]}, pluck="name"
                )
                existing_accounts_set = set(existing_accounts)
                
                # Add account details for each BPJS type
                for bpjs_type in account_types:
                    amount = bpjs_totals.get(bpjs_type, 0)
                    if amount <= 0:
                        continue
                        
                    employer_credit_field = f"{bpjs_type.lower()}_employer_credit_account"
                    if (
                        employer_credit_field in account_mapping
                        and account_mapping[employer_credit_field]
                    ):
                        account = account_mapping[employer_credit_field]
                        if account in existing_accounts_set:
                            self._add_account_detail(bpjs_type, account, amount)
        else:
            # If no company-specific mapping, use global BPJS Settings or create missing accounts
            self._create_missing_account_rows()

    def _create_missing_account_rows(self) -> None:
        """
        Helper function to create account rows when no mapping exists.
        
        Creates account details based on BPJS settings or default values.
        """
        # Get company abbreviation
        company_abbr = self._company_abbr
        
        # Get BPJS Settings
        bpjs_settings = frappe.get_single("BPJS Settings")
        
        # Calculate totals for each BPJS type
        bpjs_totals = self.doc.calculate_bpjs_type_totals()
        
        # Define component mapping
        component_mapping = {
            "BPJS Kesehatan": {
                "type": "Kesehatan",
                "account_field": "kesehatan_account",
                "default_account": f"BPJS Kesehatan Payable - {company_abbr}"
            },
            "BPJS JHT": {
                "type": "JHT",
                "account_field": "jht_account",
                "default_account": f"BPJS JHT Payable - {company_abbr}"
            },
            "BPJS JP": {
                "type": "JP",
                "account_field": "jp_account",
                "default_account": f"BPJS JP Payable - {company_abbr}"
            },
            "BPJS JKK": {
                "type": "JKK",
                "account_field": "jkk_account",
                "default_account": f"BPJS JKK Payable - {company_abbr}"
            },
            "BPJS JKM": {
                "type": "JKM",
                "account_field": "jkm_account",
                "default_account": f"BPJS JKM Payable - {company_abbr}"
            }
        }
        
        # Collect all possible account names to check
        account_names = []
        for comp in self.doc.komponen:
            if comp.component in component_mapping:
                mapping = component_mapping[comp.component]
                default_account = mapping["default_account"]
                account_names.append(default_account)
                
                # Also check settings accounts
                account_field = mapping["account_field"]
                if hasattr(bpjs_settings, account_field) and getattr(
                        bpjs_settings, account_field):
                    account_names.append(getattr(bpjs_settings, account_field))
        
        # Batch check account existence
        if account_names:
            existing_accounts = frappe.db.get_all(
                "Account", filters={"name": ["in", account_names]}, pluck="name"
            )
            existing_accounts_set = set(existing_accounts)
            
            # Add account details for each component
            for comp in self.doc.komponen:
                if comp.component in component_mapping:
                    mapping = component_mapping[comp.component]
                    bpjs_type = mapping["type"]
                    account_field = mapping["account_field"]
                    default_account = mapping["default_account"]
                    
                    # First try to use account from settings
                    account = None
                    if hasattr(bpjs_settings, account_field):
                        settings_account = getattr(bpjs_settings, account_field)
                        if settings_account in existing_accounts_set:
                            account = settings_account
                            
                    # Fall back to default account
                    if not account and default_account in existing_accounts_set:
                        account = default_account
                        
                    if account:
                        self._add_account_detail(bpjs_type, account, comp.amount)

    def _add_account_detail(self, account_type: str, account: str, 
                           amount: float) -> None:
        """
        Helper function to add a single account detail.
        
        Args:
            account_type: BPJS account type (Kesehatan, JHT, etc.)
            account: Account name
            amount: Amount for the account
        """
        if not account or amount <= 0:
            return
            
        # Format reference naming according to standard
        month_names = [
            "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", 
            "Agustus", "September", "Oktober", "November", "Desember"
        ]
        
        # Convert month to integer if it's a string
        month_num = self.doc.month
        if isinstance(month_num, str):
            try:
                month_num = int(month_num)
            except ValueError:
                month_num = 0
                
        month_name = (
            month_names[month_num - 1] if 1 <= month_num <= 12 
            else str(self.doc.month)
        )
        
        self.doc.append(
            "account_details",
            {
                "account_type": account_type,
                "account": account,
                "amount": amount,
                "reference_number": f"BPJS-{account_type}-{self.doc.month}-{self.doc.year}",
                "description": f"BPJS {account_type} {month_name} {self.doc.year}"
            }
        )

    def create_payment_entry(self) -> Optional[str]:
        """
        Create Payment Entry for BPJS Payment Summary.
        
        Creates a payment entry document to record the payment to BPJS.
        Ensures idempotency - will not create duplicate entries.
        
        Returns:
            str: Name of the created payment entry or None if not created
            
        Raises:
            frappe.ValidationError: If there's an error creating the payment entry
        """
        # Skip if Frappe is in installation/migration mode
        if getattr(frappe.flags, "in_migrate", False) or getattr(frappe.flags, 
                                                               "in_install", False):
            return None
            
        # Skip if Payment Entry table doesn't exist yet
        if not frappe.db.exists("DocType", "Payment Entry") or not frappe.db.table_exists(
                "Payment Entry"):
            debug_log("Payment Entry table does not exist yet", "BPJS Payment Service")
            return None
            
        # Check if payment entry already exists for this document
        if self.doc.payment_entry:
            pe_exists = frappe.db.exists("Payment Entry", self.doc.payment_entry)
            if pe_exists:
                debug_log(
                    f"Payment Entry {self.doc.payment_entry} already exists for "
                    f"BPJS Payment Summary {self.doc.name}",
                    "BPJS Payment Service"
                )
                return self.doc.payment_entry
                
        # Validate docstatus - doc should be submitted
        if self.doc.docstatus != 1:
            frappe.throw(_("Document must be submitted to create Payment Entry"))
            
        # Validate supplier exists
        if not frappe.db.exists("Supplier", "BPJS"):
            frappe.throw(_("BPJS Supplier does not exist"))
            
        # Validate total amount
        if not self.doc.total or self.doc.total <= 0:
            frappe.throw(_("Total amount must be greater than 0"))
            
        try:
            # Get company default accounts
            company_defaults = frappe.get_cached_value(
                "Company", 
                self.doc.company,
                ["default_bank_account", "default_payable_account", "cost_center"],
                as_dict=1
            )
            
            if not company_defaults.default_bank_account:
                frappe.throw(_("Default Bank Account not set for Company {0}").format(
                    self.doc.company))
                
            if not company_defaults.default_payable_account:
                frappe.throw(_("Default Payable Account not set for Company {0}").format(
                    self.doc.company))
                
            # Create new Payment Entry
            pe = frappe.new_doc("Payment Entry")
            pe.payment_type = "Pay"
            pe.mode_of_payment = "Bank Draft"
            pe.paid_from = company_defaults.default_bank_account
            pe.paid_to = company_defaults.default_payable_account
            pe.paid_amount = self.doc.total
            pe.received_amount = self.doc.total
            pe.reference_no = f"BPJS-{self.doc.month}-{self.doc.year}"
            pe.reference_date = self.doc.posting_date
            pe.party_type = "Supplier"
            pe.party = "BPJS"
            pe.company = self.doc.company
            
            # Get month name for remarks
            month_names = [
                "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", 
                "Agustus", "September", "Oktober", "November", "Desember"
            ]
            
            month_num = self.doc.month if isinstance(self.doc.month, int) else int(self.doc.month)
            month_name = (
                month_names[month_num - 1] if 1 <= month_num <= 12 
                else str(self.doc.month)
            )
            
            pe.remarks = f"Payment for BPJS contributions {month_name} {self.doc.year}"
            
            # Add payment reference
            pe.append(
                "references",
                {
                    "reference_doctype": "BPJS Payment Summary",
                    "reference_name": self.doc.name,
                    "total_amount": self.doc.total,
                    "allocated_amount": self.doc.total
                }
            )
            
            # Save the payment entry
            pe.insert()
            
            # Update the BPJS Payment Summary with the payment entry reference
            self.doc.db_set("payment_entry", pe.name)
            
            return pe.name
            
        except Exception as e:
            logger.error(
                f"Error creating Payment Entry for BPJS Payment Summary {self.doc.name}: "
                f"{str(e)}"
            )
            frappe.log_error(
                f"Error creating Payment Entry for BPJS Payment Summary {self.doc.name}: "
                f"{str(e)}\n\nTraceback: {frappe.get_traceback()}",
                "BPJS Payment Entry Error"
            )
            frappe.throw(_("Error creating Payment Entry: {0}").format(str(e)))

    def create_employer_journal(self) -> Optional[str]:
        """
        Create Journal Entry for BPJS employer contributions.
        
        Creates a journal entry to record the employer's BPJS contributions.
        Ensures idempotency - will not create duplicate entries.
        
        Returns:
            str: Name of the created journal entry or None if not created
            
        Raises:
            frappe.ValidationError: If there's an error creating the journal entry
        """
        # Skip if Frappe is in installation/migration mode
        if getattr(frappe.flags, "in_migrate", False) or getattr(frappe.flags, 
                                                              "in_install", False):
            return None
            
        # Skip if Journal Entry table doesn't exist yet
        if not frappe.db.exists("DocType", "Journal Entry") or not frappe.db.table_exists(
                "Journal Entry"):
            debug_log("Journal Entry table does not exist yet", "BPJS Payment Service")
            return None
            
        # Check if journal entry already exists for this document
        if self.doc.journal_entry:
            je_exists = frappe.db.exists("Journal Entry", self.doc.journal_entry)
            if je_exists:
                debug_log(
                    f"Journal Entry {self.doc.journal_entry} already exists for "
                    f"BPJS Payment Summary {self.doc.name}",
                    "BPJS Payment Service"
                )
                return self.doc.journal_entry
                
        # Validate docstatus - doc should be submitted
        if self.doc.docstatus != 1:
            frappe.throw(_("Document must be submitted to create Journal Entry"))
            
        # Validate account details exist
        if not self.doc.account_details or len(self.doc.account_details) == 0:
            frappe.throw(_("No account details found. Journal Entry cannot be created."))
            
        try:
            # Get BPJS settings
            bpjs_settings = frappe.get_single("BPJS Settings")
