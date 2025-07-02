# -*- coding: utf-8 -*-
# Copyright (c) 2025, PT. Innovasi Terbaik Bangsa and contributors
# For license information, please see license.txt
# Last modified: 2025-07-02 16:01:45 by dannyaudian

"""
BPJS Payment Service module.

This module provides a service façade for BPJS Payment Summary operations,
encapsulating payment and journal creation logic for better testability
and separation of concerns.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union, cast, Any

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from .bpjs_payment_utils import (
    PayableLine,
    ExpenseLine,
    collect_payable_lines,
    compute_employer_expense,
    get_month_name,
    safe_decimal,
    safe_table_exists
)

logger = logging.getLogger(__name__)


class PaymentSummaryService:
    """
    Service class for BPJS Payment Summary operations.
    
    This class encapsulates the business logic for creating payment entries
    and journal entries from BPJS Payment Summary documents, providing a
    reusable interface for both DocType methods and external callers.
    """
    
    def __init__(self, doc_or_name: Union[str, Any]) -> None:
        """
        Initialize PaymentSummaryService.
        
        Args:
            doc_or_name: BPJS Payment Summary document or document name
        """
        # Get the document if a name was provided
        if isinstance(doc_or_name, str):
            self.doc = frappe.get_doc("BPJS Payment Summary", doc_or_name)
        else:
            self.doc = doc_or_name
            
        # Ensure the document is of the correct type
        if not hasattr(self.doc, "doctype") or self.doc.doctype != "BPJS Payment Summary":
            raise ValueError("Invalid document type, expected BPJS Payment Summary")
            
        # Cache company abbreviation
        self._company_abbr = getattr(self.doc, "_company_abbr", None) or frappe.get_cached_value(
            "Company", self.doc.company, "abbr"
        )
            
    def create_payment_entry(self) -> Optional[str]:
        """
        Create Payment Entry for BPJS Payment Summary.
        
        Creates a payment entry document to record the payment to BPJS.
        Ensures idempotency - will not create duplicate entries.
        
        Returns:
            Optional[str]: Name of the created payment entry or None if not created
            
        Raises:
            frappe.ValidationError: If there's an error creating the payment entry
        """
        # Skip if Frappe is in installation/migration mode
        if getattr(frappe.flags, "in_migrate", False) or getattr(frappe.flags, 
                                                              "in_install", False):
            return None
            
        # Skip if Payment Entry table doesn't exist yet
        if not safe_table_exists(frappe.db, "Payment Entry"):
            logger.info("Payment Entry table does not exist yet")
            return None
            
        # Check if payment entry already exists for this document
        if self.doc.payment_entry:
            pe_exists = frappe.db.exists("Payment Entry", self.doc.payment_entry)
            if pe_exists:
                logger.info(
                    f"Payment Entry {self.doc.payment_entry} already exists for "
                    f"BPJS Payment Summary {self.doc.name}"
                )
                return self.doc.payment_entry
                
        # Validate docstatus - doc should be submitted
        if self.doc.docstatus != 1:
            frappe.throw(_("Document must be submitted to create Payment Entry"))
            
        # Validate supplier exists
        if not frappe.db.exists("Supplier", "BPJS"):
            frappe.throw(_("BPJS Supplier does not exist"))
            
        # Validate total amount
        if not self.doc.total or flt(self.doc.total) <= 0:
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
            pe.paid_amount = flt(self.doc.total)
            pe.received_amount = flt(self.doc.total)
            pe.reference_no = f"BPJS-{self.doc.month}-{self.doc.year}"
            pe.reference_date = self.doc.posting_date
            pe.party_type = "Supplier"
            pe.party = "BPJS"
            pe.company = self.doc.company
            
            # Get month name for remarks
            month_num = (
                int(self.doc.month) if isinstance(self.doc.month, int) 
                else int(self.doc.month)
            )
            month_name = get_month_name(month_num)
            
            pe.remarks = f"Payment for BPJS contributions {month_name} {self.doc.year}"
            
            # Add payment reference
            pe.append(
                "references",
                {
                    "reference_doctype": "BPJS Payment Summary",
                    "reference_name": self.doc.name,
                    "total_amount": flt(self.doc.total),
                    "allocated_amount": flt(self.doc.total)
                }
            )
            
            # Save the payment entry
            pe.insert()
            
            # Update the BPJS Payment Summary with the payment entry reference
            self.doc.db_set("payment_entry", pe.name)
            
            logger.info(f"Created Payment Entry {pe.name} for {self.doc.name}")
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
            Optional[str]: Name of the created journal entry or None if not created
            
        Raises:
            frappe.ValidationError: If there's an error creating the journal entry
        """
        # Skip if Frappe is in installation/migration mode
        if getattr(frappe.flags, "in_migrate", False) or getattr(frappe.flags, 
                                                             "in_install", False):
            return None
            
        # Skip if Journal Entry table doesn't exist yet
        if not safe_table_exists(frappe.db, "Journal Entry"):
            logger.info("Journal Entry table does not exist yet")
            return None
            
        # Check if journal entry already exists for this document
        if self.doc.journal_entry:
            je_exists = frappe.db.exists("Journal Entry", self.doc.journal_entry)
            if je_exists:
                logger.info(
                    f"Journal Entry {self.doc.journal_entry} already exists for "
                    f"BPJS Payment Summary {self.doc.name}"
                )
                return self.doc.journal_entry
                
        # Validate docstatus - doc should be submitted
        if self.doc.docstatus != 1:
            frappe.throw(_("Document must be submitted to create Journal Entry"))
            
        # Validate account details exist
        if not hasattr(self.doc, "account_details") or not self.doc.account_details:
            frappe.throw(_("No account details found. Journal Entry cannot be created."))
            
        try:
            # Get BPJS settings
            bpjs_settings = frappe.get_single("BPJS Settings")
            
            # Get default accounts
            company_defaults = frappe.get_cached_value(
                "Company",
                self.doc.company,
                ["default_expense_account", "default_payable_account", "cost_center"],
                as_dict=1
            )
            
            # Create Journal Entry
            je = frappe.new_doc("Journal Entry")
            je.voucher_type = "Journal Entry"
            je.company = self.doc.company
            je.posting_date = self.doc.posting_date
            
            # Format month name for description
            month_num = (
                int(self.doc.month) if isinstance(self.doc.month, int) 
                else int(self.doc.month)
            )
            month_name = get_month_name(month_num)
            
            je.user_remark = f"BPJS Contributions for {month_name} {self.doc.year}"
            
            # Calculate totals from employee_details
            employee_total, employer_total = self._calculate_contribution_totals()
            
            # Use dynamic account names for expense accounts
            company_abbr = self._company_abbr
            
            # Add expense entries (debit)
            # First for employee contributions - expense to Salary Payable
            if employee_total > 0:
                je.append(
                    "accounts",
                    {
                        "account": company_defaults.default_payable_account,
                        "debit_in_account_currency": employee_total,
                        "reference_type": "BPJS Payment Summary",
                        "reference_name": self.doc.name,
                        "cost_center": company_defaults.cost_center
                    }
                )
                
            # For employer contributions - expense to BPJS Expense parent account or fallback
            expense_account = None
            
            # Try to find BPJS Expenses parent account
            bpjs_expense_parent = f"BPJS Expenses - {company_abbr}"
            if frappe.db.exists("Account", bpjs_expense_parent):
                expense_account = bpjs_expense_parent
                
            # If not found, try settings or default
            if not expense_account:
                expense_account = (
                    bpjs_settings.expense_account
                    if hasattr(bpjs_settings, "expense_account") and bpjs_settings.expense_account
                    else company_defaults.default_expense_account
                )
                
            if employer_total > 0:
                je.append(
                    "accounts",
                    {
                        "account": expense_account,
                        "debit_in_account_currency": employer_total,
                        "reference_type": "BPJS Payment Summary",
                        "reference_name": self.doc.name,
                        "cost_center": company_defaults.cost_center
                    }
                )
                
            # Add liability entries (credit)
            payable_lines = collect_payable_lines(self.doc)
            for line in payable_lines:
                je.append(
                    "accounts",
                    {
                        "account": line.account,
                        "credit_in_account_currency": flt(line.amount),
                        "reference_type": "BPJS Payment Summary",
                        "reference_name": self.doc.name,
                        "cost_center": company_defaults.cost_center
                    }
                )
                
            # Save and submit journal entry
            je.insert()
            je.submit()
            
            # Update reference in BPJS Payment Summary
            self.doc.db_set("journal_entry", je.name)
            
            logger.info(f"Created Journal Entry {je.name} for {self.doc.name}")
            return je.name
            
        except Exception as e:
            logger.error(
                f"Error creating Journal Entry for BPJS Payment Summary {self.doc.name}: "
                f"{str(e)}"
            )
            frappe.log_error(
                f"Error creating Journal Entry for BPJS Payment Summary {self.doc.name}: "
                f"{str(e)}\n\nTraceback: {frappe.get_traceback()}",
                "BPJS Journal Entry Error"
            )
            frappe.throw(_("Error creating Journal Entry: {0}").format(str(e)))
    
    def recompute_totals(self) -> None:
        """
        Recalculate totals from employee details and update parent document.
        
        Updates the parent document with recalculated totals from employee details.
        """
        # Skip if Frappe is in installation/migration mode
        if getattr(frappe.flags, "in_migrate", False) or getattr(frappe.flags, 
                                                             "in_install", False):
            return
            
        # Skip if document is already submitted
        if self.doc.docstatus == 1:
            return
            
        # Skip if no employee details
        if not hasattr(self.doc, "employee_details") or not self.doc.employee_details:
            return
        
        try:
            # Calculate totals from employee details
            employee_total = Decimal('0')
            employer_total = Decimal('0')
            
            for detail in self.doc.employee_details:
                # Calculate detail total
                detail_total = (
                    safe_decimal(getattr(detail, "kesehatan_employee", 0)) +
                    safe_decimal(getattr(detail, "jht_employee", 0)) +
                    safe_decimal(getattr(detail, "jp_employee", 0)) +
                    safe_decimal(getattr(detail, "kesehatan_employer", 0)) +
                    safe_decimal(getattr(detail, "jht_employer", 0)) +
                    safe_decimal(getattr(detail, "jp_employer", 0)) +
                    safe_decimal(getattr(detail, "jkk", 0)) +
                    safe_decimal(getattr(detail, "jkm", 0))
                )
                
                # Update detail amount
                if hasattr(detail, "amount"):
                    detail.amount = float(detail_total)
                
                # Update contribution totals
                employee_total += (
                    safe_decimal(getattr(detail, "kesehatan_employee", 0)) +
                    safe_decimal(getattr(detail, "jht_employee", 0)) +
                    safe_decimal(getattr(detail, "jp_employee", 0))
                )
                
                employer_total += (
                    safe_decimal(getattr(detail, "kesehatan_employer", 0)) +
                    safe_decimal(getattr(detail, "jht_employer", 0)) +
                    safe_decimal(getattr(detail, "jp_employer", 0)) +
                    safe_decimal(getattr(detail, "jkk", 0)) +
                    safe_decimal(getattr(detail, "jkm", 0))
                )
                
            # Update doc totals without triggering validation
            self.doc.db_set("total_employee", float(employee_total), update_modified=False)
            self.doc.db_set("total_employer", float(employer_total), update_modified=False)
            self.doc.db_set("grand_total", float(employee_total + employer_total), 
                          update_modified=False)
            
            # If populate_from_employee_details method exists, call it
            if hasattr(self.doc, "populate_from_employee_details"):
                self.doc.populate_from_employee_details()
                
            # If set_account_details method exists, call it
            if hasattr(self.doc, "set_account_details"):
                self.doc.set_account_details()
                
            # Update last_synced timestamp
            self.doc.db_set("last_synced", now_datetime(), update_modified=False)
            
            logger.info(f"Recomputed totals for {self.doc.name}")
            
        except Exception as e:
            logger.error(f"Error recomputing totals for {self.doc.name}: {str(e)}")
            frappe.log_error(
                f"Error recomputing totals for {self.doc.name}: {str(e)}\n\n"
                f"Traceback: {frappe.get_traceback()}",
                "BPJS Total Recalculation Error"
            )
    
    def _calculate_contribution_totals(self) -> Tuple[float, float]:
        """
        Calculate employee and employer contribution totals.
        
        Returns:
            Tuple[float, float]: (employee_total, employer_total)
        """
        employee_total = 0
        employer_total = 0
        
        if hasattr(self.doc, "employee_details") and self.doc.employee_details:
            for detail in self.doc.employee_details:
                # Sum up employee contributions
                employee_total += (
                    flt(getattr(detail, "kesehatan_employee", 0)) +
                    flt(getattr(detail, "jht_employee", 0)) +
                    flt(getattr(detail, "jp_employee", 0))
                )
                
                # Sum up employer contributions
                employer_total += (
                    flt(getattr(detail, "kesehatan_employer", 0)) +
                    flt(getattr(detail, "jht_employer", 0)) +
                    flt(getattr(detail, "jp_employer", 0)) +
                    flt(getattr(detail, "jkk", 0)) +
                    flt(getattr(detail, "jkm", 0))
                )
                
        return employee_total, employer_total
