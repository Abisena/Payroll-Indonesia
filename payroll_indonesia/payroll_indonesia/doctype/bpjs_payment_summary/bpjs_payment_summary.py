# -*- coding: utf-8 -*-
# Copyright (c) 2025, PT. Innovasi Terbaik Bangsa and contributors
# For license information, please see license.txt
# Last modified: 2025-07-02 15:39:47 by dannyaudian

"""
BPJS Payment Summary DocType controller.

This module defines the BPJSPaymentSummary document class and associated service layer
for managing BPJS (social security) payment summaries, including generating journal entries
and payment entries.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TypedDict, Union, cast

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_last_day, now_datetime, today

from .bpjs_payment_service import PaymentSummaryService
from .bpjs_payment_utils import debug_log
from .bpjs_payment_validation import create_bpjs_supplier

# Configure logger
logger = logging.getLogger(__name__)


class BPJSContributionData(TypedDict, total=False):
    """Type definition for BPJS contribution data."""
    jht_employee: float
    jp_employee: float
    kesehatan_employee: float
    jht_employer: float
    jp_employer: float
    kesehatan_employer: float
    jkk: float
    jkm: float


class BPJSPaymentSummary(Document):
    """
    BPJS Payment Summary DocType controller.
    
    This class handles the management of BPJS payment summaries, including validation,
    calculation of contribution totals, and creation of associated accounting entries.
    """
    
    def validate(self) -> None:
        """
        Validate document before save/submit.
        
        Performs all validation checks and sets default values where needed.
        """
        # Ensure month and year are integers
        if self.month and isinstance(self.month, str):
            try:
                self.month = int(self.month)
            except (ValueError, TypeError):
                frappe.throw(_("Month must be a valid number"))

        if self.year and isinstance(self.year, str):
            try:
                self.year = int(self.year)
            except (ValueError, TypeError):
                frappe.throw(_("Year must be a valid number"))

        self.set_missing_values()
        self.validate_company()
        self.validate_month_year()
        self.check_and_generate_components()
        self.calculate_total()
        self.validate_total()
        self.validate_supplier()
        self.set_account_details()

    def set_missing_values(self) -> None:
        """
        Set default values for required fields.
        
        Populates empty fields with appropriate default values.
        """
        # Set posting_date if empty
        if not self.posting_date:
            self.posting_date = today()

        # Set month name and title if fields exist
        if hasattr(self, "month") and hasattr(self, "year") and self.month and self.year:
            month_names = [
                "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", 
                "Agustus", "September", "Oktober", "November", "Desember"
            ]

            if 1 <= self.month <= 12:
                # Set month_name if field exists
                if hasattr(self, "month_name"):
                    self.month_name = month_names[self.month - 1]

                # Set month_year_title if field exists
                if hasattr(self, "month_year_title"):
                    self.month_year_title = f"{month_names[self.month - 1]} {self.year}"

    def validate_company(self) -> None:
        """
        Validate company and its default accounts.
        
        Ensures the company exists and has required default accounts set up.
        
        Raises:
            frappe.ValidationError: If company is missing or accounts are not properly set.
        """
        if not self.company:
            frappe.throw(_("Company is mandatory"))

        # Check default accounts
        company_doc = frappe.get_doc("Company", self.company)
        if not company_doc.default_bank_account:
            frappe.throw(
                _("Default Bank Account not set for Company {0}").format(self.company)
            )
        if not company_doc.default_payable_account:
            frappe.throw(
                _("Default Payable Account not set for Company {0}").format(self.company)
            )

        # Store company abbreviation for later use
        self._company_abbr = frappe.get_cached_value("Company", self.company, "abbr")

    def validate_month_year(self) -> None:
        """
        Ensure month and year are valid.
        
        Raises:
            frappe.ValidationError: If month/year values are invalid.
        """
        if not self.month or not self.year:
            frappe.throw(_("Both Month and Year are mandatory"))
        if self.month < 1 or self.month > 12:
            frappe.throw(_("Month must be between 1 and 12"))
        if self.year < 2000:
            frappe.throw(_("Year must be greater than or equal to 2000"))

    def check_and_generate_components(self) -> None:
        """
        Validate BPJS components and auto-generate if needed.
        
        Creates component entries from employee details or adds default components
        if none exist.
        """
        # If components are empty but employee_details exist, auto-generate components
        if (not self.komponen or len(self.komponen) == 0) and hasattr(self, 
                "employee_details") and self.employee_details:
            self.populate_from_employee_details()

        # If still empty, add default component
        if not self.komponen or len(self.komponen) == 0:
            self.append(
                "komponen",
                {
                    "component": "BPJS JHT",
                    "component_type": "JHT",
                    "amount": flt(self.amount) if hasattr(self, "amount") and self.amount else 0
                }
            )
            debug_log(f"Added default component for BPJS Payment Summary {self.name}")
        else:
            # Ensure all components have component_type
            for comp in self.komponen:
                if not comp.component_type:
                    comp.component_type = comp.component.replace("BPJS ", "")
                if not comp.amount or comp.amount <= 0:
                    frappe.throw(_("Component amount must be greater than 0"))

    def populate_from_employee_details(self) -> bool:
        """
        Generate komponen entries from employee_details data.
        
        Returns:
            bool: True if components were successfully generated, False otherwise.
        """
        if not hasattr(self, "employee_details") or not self.employee_details:
            return False

        # Reset existing komponen child table
        self.komponen = []

        # Calculate totals for each BPJS type
        bpjs_totals = {"Kesehatan": 0, "JHT": 0, "JP": 0, "JKK": 0, "JKM": 0}

        # Calculate from employee_details
        for emp in self.employee_details:
            bpjs_totals["Kesehatan"] += flt(emp.kesehatan_employee) + flt(
                emp.kesehatan_employer)
            bpjs_totals["JHT"] += flt(emp.jht_employee) + flt(emp.jht_employer)
            bpjs_totals["JP"] += flt(emp.jp_employee) + flt(emp.jp_employer)
            bpjs_totals["JKK"] += flt(emp.jkk)
            bpjs_totals["JKM"] += flt(emp.jkm)

        # Map BPJS types to component names
        component_name_map = {
            "Kesehatan": "BPJS Kesehatan",
            "JHT": "BPJS JHT",
            "JP": "BPJS JP",
            "JKK": "BPJS JKK",
            "JKM": "BPJS JKM"
        }

        # Add components
        has_components = False
        for bpjs_type, amount in bpjs_totals.items():
            amount = flt(amount)
            if amount > 0:
                component_name = component_name_map.get(bpjs_type)
                if component_name:
                    self.append(
                        "komponen",
                        {
                            "component": component_name,
                            "component_type": bpjs_type,
                            "amount": amount
                        }
                    )
                    has_components = True

        # If no valid components, create default component
        if not has_components:
            self.append(
                "komponen", 
                {"component": "BPJS JHT", "component_type": "JHT", "amount": 0}
            )

        return True

    def calculate_total(self) -> None:
        """
        Calculate total from components and set amount field.
        
        Sums up all component amounts to determine the total payment amount.
        """
        # Validate komponen exists
        if not hasattr(self, "komponen") or not self.komponen:
            self.total = 0
            return

        # Continue with calculation
        self.total = sum(flt(d.amount) for d in self.komponen)

    def validate_total(self) -> None:
        """
        Validate total amount is greater than 0.
        
        Raises:
            frappe.ValidationError: If total amount is zero or negative.
        """
        if not self.total or self.total <= 0:
            frappe.throw(_("Total amount must be greater than 0"))

    def validate_supplier(self) -> None:
        """
        Validate BPJS supplier exists.
        
        Creates a default BPJS supplier if one doesn't exist yet.
        """
        if not frappe.db.exists("Supplier", "BPJS"):
            create_bpjs_supplier()

    def set_account_details(self) -> None:
        """
        Set account details from BPJS Settings and Account Mapping.
        
        Populates account_details child table based on company settings and mappings.
        
        Raises:
            frappe.ValidationError: If there's an error setting account details.
        """
        if self.docstatus == 1:
            frappe.throw(_("Cannot modify account details after submission"))

        # Get company abbreviation
        company_abbr = getattr(self, "_company_abbr", None) or frappe.get_cached_value(
            "Company", self.company, "abbr"
        )
        self._company_abbr = company_abbr

        # Clear existing account_details
        self.account_details = []

        try:
            service = PaymentSummaryService(self)
            service.set_account_details()
        except Exception as e:
            logger.error(
                f"Error setting account details for BPJS Payment Summary {self.name}: {str(e)}"
            )
            frappe.log_error(
                f"Error setting account details for BPJS Payment Summary {self.name}: {str(e)}\n\n"
                f"Traceback: {frappe.get_traceback()}",
                "BPJS Account Details Error"
            )
            frappe.throw(_("Error setting account details: {0}").format(str(e)))

    def before_save(self) -> None:
        """
        Ensure all required fields are set before saving.
        
        Updates last_synced timestamp if applicable.
        """
        # Update last_synced if it exists
        if hasattr(self, "last_synced") and not self.last_synced:
            self.last_synced = now_datetime()

    def on_submit(self) -> None:
        """
        Actions to perform on document submission.
        
        Sets status to Submitted and creates payment entry.
        """
        self.status = "Submitted"
        self.create_payment_entry()

    def on_cancel(self) -> None:
        """
        Actions to perform on document cancellation.
        
        Validates linked entries and resets status to Draft.
        
        Raises:
            frappe.ValidationError: If linked entries are already submitted.
        """
        if self.payment_entry:
            pe_status = frappe.db.get_value("Payment Entry", self.payment_entry, "docstatus")
            if pe_status and int(pe_status) == 1:
                frappe.throw(_("Cannot cancel document with submitted Payment Entry"))

        if self.journal_entry:
            je_status = frappe.db.get_value("Journal Entry", self.journal_entry, "docstatus")
            if je_status and int(je_status) == 1:
                frappe.throw(
                    _("Cannot cancel document with submitted Journal Entry. "
                      "Cancel the Journal Entry first.")
                )

        self.status = "Draft"

    @frappe.whitelist()
    def create_payment_entry(self) -> Dict[str, Any]:
        """
        Create Payment Entry for BPJS Payment Summary.
        
        Creates a payment entry document to record the payment to BPJS.
        Uses the PaymentSummaryService to ensure idempotency.
        
        Returns:
            dict: Result with status and payment entry name.
        
        Raises:
            frappe.ValidationError: If there's an error creating the payment entry.
        """
        try:
            service = PaymentSummaryService(self)
            payment_entry_name = service.create_payment_entry()
            
            if payment_entry_name:
                result = {
                    "success": True, 
                    "payment_entry": payment_entry_name,
                    "message": _("Payment Entry {0} created successfully").format(
                        payment_entry_name)
                }
            else:
                result = {
                    "success": False,
                    "message": _("No Payment Entry was created")
                }
                
            return result
        except Exception as e:
            logger.error(
                f"Error creating Payment Entry for BPJS Payment Summary {self.name}: {str(e)}"
            )
            frappe.log_error(
                f"Error creating Payment Entry for BPJS Payment Summary {self.name}: {str(e)}\n\n"
                f"Traceback: {frappe.get_traceback()}",
                "BPJS Payment Entry Error"
            )
            return {
                "success": False,
                "message": _("Error creating Payment Entry: {0}").format(str(e))
            }

    @frappe.whitelist()
    def create_employer_journal(self) -> Dict[str, Any]:
        """
        Create Journal Entry for BPJS employer contributions.
        
        Creates a journal entry to record the employer's portion of BPJS contributions.
        Uses the PaymentSummaryService to ensure idempotency.
        
        Returns:
            dict: Result with status and journal entry name.
            
        Raises:
            frappe.ValidationError: If there's an error creating the journal entry.
        """
        try:
            service = PaymentSummaryService(self)
            journal_entry_name = service.create_employer_journal()
            
            if journal_entry_name:
                result = {
                    "success": True, 
                    "journal_entry": journal_entry_name,
                    "message": _("Journal Entry {0} created successfully").format(
                        journal_entry_name)
                }
            else:
                result = {
                    "success": False,
                    "message": _("No Journal Entry was created")
                }
                
            return result
        except Exception as e:
            logger.error(
                f"Error creating Journal Entry for BPJS Payment Summary {self.name}: {str(e)}"
            )
            frappe.log_error(
                f"Error creating Journal Entry for BPJS Payment Summary {self.name}: {str(e)}\n\n"
                f"Traceback: {frappe.get_traceback()}",
                "BPJS Journal Entry Error"
            )
            return {
                "success": False,
                "message": _("Error creating Journal Entry: {0}").format(str(e))
            }

    @frappe.whitelist()
    def get_from_salary_slip(self) -> Dict[str, Any]:
        """
        Get BPJS data from salary slips for the specified period.
        
        Fetches data from salary slips and populates employee_details.
        
        Returns:
            dict: Result with status and count.
            
        Raises:
            frappe.ValidationError: If there's an error fetching data.
        """
        if self.docstatus > 0:
            frappe.throw(_("Cannot fetch data after submission"))

        # Validate required fields
        if not self.company:
            frappe.throw(_("Company is required"))

        if not self.month or not self.year:
            frappe.throw(_("Month and Year are required"))

        try:
            # Clear existing employee details
            self.employee_details = []

            # Get salary slips based on filter
            salary_slips = self._get_filtered_salary_slips()

            if not salary_slips:
                frappe.msgprint(_("No salary slips found for the selected period"))
                return {"success": False, "count": 0}

            # Process each salary slip
            employees_processed = []

            for slip in salary_slips:
                # Skip if employee already processed (to avoid duplicates)
                if slip.employee in employees_processed:
                    continue

                # Extract BPJS data from salary slip
                bpjs_data = self._extract_bpjs_from_salary_slip(slip)

                if bpjs_data:
                    # Add employee to processed list
                    employees_processed.append(slip.employee)

                    # Add to employee_details table
                    self.append(
                        "employee_details",
                        {
                            "employee": slip.employee,
                            "employee_name": slip.employee_name,
                            "salary_slip": slip.name,
                            "jht_employee": bpjs_data.get("jht_employee", 0),
                            "jp_employee": bpjs_data.get("jp_employee", 0),
                            "kesehatan_employee": bpjs_data.get("kesehatan_employee", 0),
                            "jht_employer": bpjs_data.get("jht_employer", 0),
                            "jp_employer": bpjs_data.get("jp_employer", 0),
                            "kesehatan_employer": bpjs_data.get("kesehatan_employer", 0),
                            "jkk": bpjs_data.get("jkk", 0),
                            "jkm": bpjs_data.get("jkm", 0),
                            "last_updated": now_datetime(),
                            "is_synced": 1
                        }
                    )

            # Regenerate components and account details from employee_details
            if employees_processed:
                self.populate_from_employee_details()
                self.set_account_details()
                self.calculate_total()

                # Set last_synced timestamp
                self.last_synced = now_datetime()

                # Save the document
                self.save()

                return {"success": True, "count": len(employees_processed)}
            else:
                return {
                    "success": False, 
                    "count": 0, 
                    "message": "No valid BPJS data found"
                }

        except Exception as e:
            logger.error(f"Error fetching data from salary slips for {self.name}: {str(e)}")
            frappe.log_error(
                f"Error fetching data from salary slips for {self.name}: {str(e)}\n\n"
                f"Traceback: {frappe.get_traceback()}",
                "BPJS Salary Slip Fetch Error"
            )
            frappe.throw(_("Error fetching data from salary slips: {0}").format(str(e)))

    def _get_filtered_salary_slips(self) -> List[Dict[str, Any]]:
        """
        Get salary slips based on filter criteria.
        
        Returns:
            list: List of salary slip documents matching the filter criteria.
        """
        filters = {"docstatus": 1, "company": self.company}

        # Convert month and year to integers
        month = int(self.month) if isinstance(self.month, str) else self.month
        year = int(self.year) if isinstance(self.year, str) else self.year

        # Add date-based filters
        if hasattr(self, "salary_slip_filter") and self.salary_slip_filter:
            if self.salary_slip_filter == "Periode Saat Ini":
                # Get slips for current month and year
                filters.update({
                    "start_date": ["between", [
                        f"{year}-{month:02d}-01",
                        get_last_day(f"{year}-{month:02d}-01")
                    ]]
                })
            elif self.salary_slip_filter == "Periode Kustom":
                # Custom period - use custom fields if available or default to month range
                if (hasattr(self, "from_date") and hasattr(self, "to_date") and 
                        self.from_date and self.to_date):
                    filters.update({
                        "start_date": [">=", self.from_date], 
                        "end_date": ["<=", self.to_date]
                    })
                else:
                    # Default to current month
                    filters.update({
                        "start_date": ["between", [
                            f"{year}-{month:02d}-01",
                            get_last_day(f"{year}-{month:02d}-01")
                        ]]
                    })
            elif self.salary_slip_filter == "Semua Slip Belum Terbayar":
                # Get all slips not linked to a BPJS payment
                # This is more complex, so instead of filtering, we'll get all slips
                # and filter later in code
                pass
        else:
            # Default to current month
            filters.update({
                "start_date": ["between", [
                    f"{year}-{month:02d}-01",
                    get_last_day(f"{year}-{month:02d}-01")
                ]]
            })

        # Get salary slips based on filters
        salary_slips = frappe.get_all(
            "Salary Slip",
            filters=filters,
            fields=["name", "employee", "employee_name", "start_date", "end_date"]
        )

        # For "Semua Slip Belum Terbayar" filter, filter out slips already linked
        # to other BPJS payments
        if (hasattr(self, "salary_slip_filter") and 
                self.salary_slip_filter == "Semua Slip Belum Terbayar"):
            # Get list of salary slips already linked to BPJS payments
            linked_slips = frappe.get_all(
                "BPJS Payment Summary Detail",
                filters={"docstatus": 1, "salary_slip": ["is", "set"]},
                fields=["salary_slip"]
            )
            linked_slip_names = [slip.salary_slip for slip in linked_slips if slip.salary_slip]

            # Filter out already linked slips
            salary_slips = [slip for slip in salary_slips if slip.name not in linked_slip_names]

        return salary_slips

    def _extract_bpjs_from_salary_slip(self, slip: Dict[str, Any]) -> Optional[BPJSContributionData]:
        """
        Extract BPJS data from a salary slip.
        
        Args:
            slip: Salary slip document or dict
            
        Returns:
            dict: BPJS contribution data or None if no data found
        """
        # Get the full salary slip document
        doc = frappe.get_doc("Salary Slip", slip.name)

        bpjs_data: BPJSContributionData = {
            "jht_employee": 0,
            "jp_employee": 0,
            "kesehatan_employee": 0,
            "jht_employer": 0,
            "jp_employer": 0,
            "kesehatan_employer": 0,
            "jkk": 0,
            "jkm": 0
        }

        # Extract employee contributions from deductions
        if hasattr(doc, "deductions") and doc.deductions:
            for d in doc.deductions:
                if ("BPJS Kesehatan" in d.salary_component and 
                        "Employee" not in d.salary_component):
                    bpjs_data["kesehatan_employee"] += flt(d.amount)
                elif "BPJS JHT" in d.salary_component and "Employee" not in d.salary_component:
                    bpjs_data["jht_employee"] += flt(d.amount)
                elif "BPJS JP" in d.salary_component and "Employee" not in d.salary_component:
                    bpjs_data["jp_employee"] += flt(d.amount)
                # Support alternative naming with "Employee" suffix
                elif "BPJS Kesehatan Employee" in d.salary_component:
                    bpjs_data["kesehatan_employee"] += flt(d.amount)
                elif "BPJS JHT Employee" in d.salary_component:
                    bpjs_data["jht_employee"] += flt(d.amount)
                elif "BPJS JP Employee" in d.salary_component:
                    bpjs_data["jp_employee"] += flt(d.amount)

        # Extract employer contributions from earnings or statistical components
        if hasattr(doc, "earnings") and doc.earnings:
            for e in doc.earnings:
                if "BPJS Kesehatan Employer" in e.salary_component:
                    bpjs_data["kesehatan_employer"] += flt(e.amount)
                elif "BPJS JHT Employer" in e.salary_component:
                    bpjs_data["jht_employer"] += flt(e.amount)
                elif "BPJS JP Employer" in e.salary_component:
                    bpjs_data["jp_employer"] += flt(e.amount)
                elif "BPJS JKK" in e.salary_component:
                    bpjs_data["jkk"] += flt(e.amount)
                elif "BPJS JKM" in e.salary_component:
                    bpjs_data["jkm"] += flt(e.amount)

        # Check if we found any BPJS data
        has_data = any(flt(value) > 0 for value in bpjs_data.values())
        return bpjs_data if has_data else None

    @frappe.whitelist()
    def update_from_salary_slip(self) -> Dict[str, Any]:
        """
        Update BPJS data from linked salary slips.
        
        Updates employee_details with the latest data from linked salary slips.
        
        Returns:
            dict: Result with status and counts.
            
        Raises:
            frappe.ValidationError: If there's an error updating data.
        """
        if self.docstatus > 0:
            frappe.throw(_("Cannot update data after submission"))

        if not hasattr(self, "employee_details") or not self.employee_details:
            frappe.throw(_("No employee details to update"))

        try:
            count = 0
            updated = 0

            for emp_detail in self.employee_details:
                count += 1

                # Skip records without salary slip
                if not emp_detail.salary_slip:
                    continue

                # Check if slip exists
                if not frappe.db.exists("Salary Slip", emp_detail.salary_slip):
                    continue

                # Get BPJS data from salary slip
                slip = frappe.get_doc("Salary Slip", emp_detail.salary_slip)
                bpjs_data = self._extract_bpjs_from_salary_slip(slip)

                if bpjs_data:
                    # Update employee details row
                    emp_detail.jht_employee = bpjs_data.get("jht_employee", 0)
                    emp_detail.jp_employee = bpjs_data.get("jp_employee", 0)
                    emp_detail.kesehatan_employee = bpjs_data.get("kesehatan_employee", 0)
                    emp_detail.jht_employer = bpjs_data.get("jht_employer", 0)
                    emp_detail.jp_employer = bpjs_data.get("jp_employer", 0)
                    emp_detail.kesehatan_employer = bpjs_data.get("kesehatan_employer", 0)
                    emp_detail.jkk = bpjs_data.get("jkk", 0)
                    emp_detail.jkm = bpjs_data.get("jkm", 0)
                    emp_detail.last_updated = now_datetime()
                    emp_detail.is_synced = 1

                    updated += 1

            # Regenerate components and account details from employee_details
            if updated > 0:
                self.populate_from_employee_details()
                self.set_account_details()
                self.calculate_total()
                self.last_synced = now_datetime()
                self.save()

            return {"success": True, "count": count, "updated": updated}

        except Exception as e:
            logger.error(f"Error updating data from salary slips for {self.name}: {str(e)}")
            frappe.log_error(
                f"Error updating data from salary slips for {self.name}: {str(e)}\n\n"
                f"Traceback: {frappe.get_traceback()}",
                "BPJS Salary Slip Update Error"
            )
            frappe.throw(_("Error updating data from salary slips: {0}").format(str(e)))

    @frappe.whitelist()
    def populate_employee_details(self) -> Dict[str, Any]:
        """
        Populate employee details with active employees having BPJS participation.
        
        Returns:
            dict: Result with success status and count.
            
        Raises:
            frappe.ValidationError: If there's an error populating employee details.
        """
        if self.docstatus > 0:
            frappe.throw(_("Cannot modify employee details after submission"))

        # Check if we already have employee details
        if hasattr(self, "employee_details") and self.employee_details:
            frappe.confirm(
                _("This will replace existing employee details. Continue?"),
                yes_callback=lambda: self._populate_employee_details_confirmed(),
                no_callback=lambda: frappe.msgprint(_("Operation cancelled")),
            )
        else:
            return self._populate_employee_details_confirmed()

    def _populate_employee_details_confirmed(self) -> Dict[str, Any]:
        """
        Implementation of populate_employee_details after confirmation.
        
        Returns:
            dict: Result with success status and count.
        
        Raises:
            frappe.ValidationError: If there's an error populating employee details.
        """
        try:
            # Get active employees with BPJS participation
            employees = frappe.get_all(
                "Employee",
                filters={"status": "Active", "company": self.company},
                fields=["name", "employee_name"]
            )

            # Clear existing employee details
            self.employee_details = []

            # Add employees to details
            for emp in employees:
                # Check if employee has BPJS settings
                has_bpjs = False

                # Check custom fields for BPJS participation if they exist
                participation_fields = [
                    "bpjs_jht_participation",
                    "bpjs_jp_participation",
                    "bpjs_kesehatan_participation",
                    "custom_bpjs_participation"
                ]

                for field in participation_fields:
                    if frappe.db.has_column("Employee", field):
                        value = frappe.db.get_value("Employee", emp.name, field)
                        if value:
                            has_bpjs = True
                            break

                # If no specific BPJS fields or all are false, assume participation
                if not has_bpjs:
                    has_bpjs = True  # Default to true if no specific fields

                if has_bpjs:
                    # Get salary structure for this employee
                    salary_structure = frappe.db.get_value(
                        "Salary Structure Assignment",
                        {"employee": emp.name, "docstatus": 1},
                        "salary_structure"
                    )

                    # Calculate estimated BPJS amounts
                    bpjs_amounts = self._calculate_employee_bpjs_amounts(
                        emp.name, salary_structure)

                    # Add to employee_details table
                    self.append(
                        "employee_details",
                        {
                            "employee": emp.name,
                            "employee_name": emp.employee_name,
                            "jht_employee": bpjs_amounts.get("jht_employee", 0),
                            "jp_employee": bpjs_amounts.get("jp_employee", 0),
                            "kesehatan_employee": bpjs_amounts.get("kesehatan_employee", 0),
                            "jht_employer": bpjs_amounts.get("jht_employer", 0),
                            "jp_employer": bpjs_amounts.get("jp_employer", 0),
                            "kesehatan_employer": bpjs_amounts.get("kesehatan_employer", 0),
                            "jkk": bpjs_amounts.get("jkk", 0),
                            "jkm": bpjs_amounts.get("jkm", 0),
                            "last_updated": now_datetime()
                        }
                    )

            # Regenerate components from employee_details
            self.populate_from_employee_details()
            self.calculate_total()

            self.save()

            return {"success": True, "count": len(self.employee_details)}

        except Exception as e:
            logger.error(f"Error populating employee details for {self.name}: {str(e)}")
            frappe.log_error(
                f"Error populating employee details for {self.name}: {str(e)}\n\n"
                f"Traceback: {frappe.get_traceback()}",
                "BPJS Employee Details Error"
            )
            frappe.throw(_("Error populating employee details: {0}").format(str(e)))

    def _calculate_employee_bpjs_amounts(
        self, employee: str, salary_structure: Optional[str] = None
    ) -> BPJSContributionData:
        """
        Calculate estimated BPJS amounts for an employee.
        
        Args:
            employee: Employee ID
            salary_structure: Salary structure name (optional)
            
        Returns:
            dict: BPJS contribution amounts
        """
        # Default empty result
        result: BPJSContributionData = {
            "jht_employee": 0,
            "jp_employee": 0,
            "kesehatan_employee": 0,
            "jht_employer": 0,
            "jp_employer": 0,
            "kesehatan_employer": 0,
            "jkk": 0,
            "jkm": 0
        }

        try:
            # Get BPJS settings
            bpjs_settings = frappe.get_single("BPJS Settings")

            # Get base salary or total earnings from the most recent salary slip
            base_salary = 0

            # Try to find recent salary slip first
            recent_slip = frappe.get_all(
                "Salary Slip",
                filters={"employee": employee, "docstatus": 1},
                fields=["name", "base_salary", "gross_pay"],
                order_by="start_date desc",
                limit=1
            )

            if recent_slip:
                base_salary = recent_slip[0].base_salary or recent_slip[0].gross_pay
            else:
                # If no slip found, try to get from salary structure
                if salary_structure:
                    base_components = frappe.get_all(
                        "Salary Detail",
                        filters={
                            "parent": salary_structure,
                            "parentfield": "earnings",
                            "is_base_component": 1
                        },
                        fields=["amount"]
                    )

                    if base_components:
                        base_salary = sum(flt(comp.amount) for comp in base_components)
                    else:
                        # Try to get from assignment
                        assignment = frappe.get_all(
                            "Salary Structure Assignment",
                            filters={"employee": employee, "docstatus": 1},
                            fields=["base"],
                            order_by="from_date desc",
                            limit=1
                        )

                        if assignment:
                            base_salary = assignment[0].base

            # If still no base salary, exit with zeroes
            if not base_salary or base_salary <= 0:
                return result

            # Calculate BPJS amounts based on settings
            # These values will be defaults if no specific rates found in settings
            jht_employee_rate = 0.02  # 2%
            jht_employer_rate = 0.037  # 3.7%
            jp_employee_rate = 0.01  # 1%
            jp_employer_rate = 0.02  # 2%
            kesehatan_employee_rate = 0.01  # 1%
            kesehatan_employer_rate = 0.04  # 4%
            jkk_rate = 0.0054  # 0.54%
            jkm_rate = 0.003  # 0.3%

            # Apply rates from BPJS settings if available
            if hasattr(bpjs_settings, "jht_employee_percent"):
                jht_employee_rate = flt(bpjs_settings.jht_employee_percent) / 100
            if hasattr(bpjs_settings, "jht_employer_percent"):
                jht_employer_rate = flt(bpjs_settings.jht_employer_percent) / 100
            if hasattr(bpjs_settings, "jp_employee_percent"):
                jp_employee_rate = flt(bpjs_settings.jp_employee_percent) / 100
            if hasattr(bpjs_settings, "jp_employer_percent"):
                jp_employer_rate = flt(bpjs_settings.jp_employer_percent) / 100
            if hasattr(bpjs_settings, "kesehatan_employee_percent"):
                kesehatan_employee_rate = flt(bpjs_settings.kesehatan_employee_percent) / 100
            if hasattr(bpjs_settings, "kesehatan_employer_percent"):
                kesehatan_employer_rate = flt(bpjs_settings.kesehatan_employer_percent) / 100
            if hasattr(bpjs_settings, "jkk_percent"):
                jkk_rate = flt(bpjs_settings.jkk_percent) / 100
            if hasattr(bpjs_settings, "jkm_percent"):
                jkm_rate = flt(bpjs_settings.jkm_percent) / 100

            # Calculate BPJS amounts
            result = {
                "jht_employee": flt(base_salary * jht_employee_rate),
                "jp_employee": flt(base_salary * jp_employee_rate),
                "kesehatan_employee": flt(base_salary * kesehatan_employee_rate),
                "jht_employer": flt(base_salary * jht_employer_rate),
                "jp_employer": flt(base_salary * jp_employer_rate),
                "kesehatan_employer": flt(base_salary * kesehatan_employer_rate),
                "jkk": flt(base_salary * jkk_rate),
                "jkm": flt(base_salary * jkm_rate)
            }

            return result

        except Exception as e:
            logger.error(f"Error calculating BPJS amounts for employee {employee}: {str(e)}")
            frappe.log_error(
                f"Error calculating BPJS amounts for employee {employee}: {str(e)}\n\n"
                f"Traceback: {frappe.get_traceback()}",
                "BPJS Amount Calculation Error"
            )
            return result

    def calculate_bpjs_type_totals(self) -> Dict[str, float]:
        """
        Calculate totals for each BPJS type from components or employee details.
        
        Returns:
            dict: BPJS type totals
        """
        bpjs_totals = {"Kesehatan": 0, "JHT": 0, "JP": 0, "JKK": 0, "JKM": 0}

        # Calculate from employee_details if available
        if hasattr(self, "employee_details") and self.employee_details:
            for emp in self.employee_details:
                bpjs_totals["Kesehatan"] += flt(emp.kesehatan_employee) + flt(
                    emp.kesehatan_employer)
                bpjs_totals["JHT"] += flt(emp.jht_employee) + flt(emp.jht_employer)
                bpjs_totals["JP"] += flt(emp.jp_employee) + flt(emp.jp_employer)
                bpjs_totals["JKK"] += flt(emp.jkk)
                bpjs_totals["JKM"] += flt(emp.jkm)
        else:
            # If no employee_details, use data from components
            component_type_map = {
                "BPJS Kesehatan": "Kesehatan",
                "BPJS JHT": "JHT",
                "BPJS JP": "JP",
                "BPJS JKK": "JKK",
                "BPJS JKM": "JKM"
            }

            for comp in self.komponen:
                bpjs_type = comp.component_type or component_type_map.get(comp.component)
                if bpjs_type:
                    bpjs_totals[bpjs_type] += flt(comp.amount)

        return bpjs_totals

    def _calculate_contribution_totals(self) -> Tuple[float, float]:
        """
        Calculate employee and employer contribution totals.
        
        Returns:
            tuple: (employee_total, employer_total)
        """
        employee_total = 0
        employer_total = 0

        if hasattr(self, "employee_details") and self.employee_details:
            for d in self.employee_details:
                # Sum up employee contributions
                employee_total += (
                    flt(d.kesehatan_employee) + flt(d.jht_employee) + flt(d.jp_employee)
                )

                # Sum up employer contributions
                employer_total += (
                    flt(d.kesehatan_employer)
                    + flt(d.jht_employer)
                    + flt(d.jp_employer)
                    + flt(d.jkk)
                    + flt(d.jkm)
                )

        return employee_total, employer_total


@frappe.whitelist()
def get_bpjs_suppliers() -> List[Dict[str, Any]]:
    """
    Get list of BPJS suppliers.
    
    Returns a list of BPJS suppliers or creates default one if not exists.
    
    Returns:
        list: List of BPJS suppliers
    """
    try:
        # Check if BPJS supplier exists
        if not frappe.db.exists("Supplier", "BPJS"):
            # Create default BPJS supplier if not exists
            create_bpjs_supplier()

        # Query for suppliers with "BPJS" in their name
        suppliers = frappe.get_all(
            "Supplier",
            filters=[["name", "like", "%BPJS%"]],
            fields=["name", "supplier_name", "supplier_type"]
        )

        return suppliers
    except Exception as e:
        logger.error(f"Error in get_bpjs_suppliers: {str(e)}")
        frappe.log_error(
            f"Error in get_bpjs_suppliers: {str(e)}\n\n" 
            f"Traceback: {frappe.get_traceback()}",
            "BPJS Suppliers Error"
        )
        return []


@frappe.whitelist()
def validate(doc: Union[str, Document], method: Optional[str] = None) -> bool:
    """
    Module-level validate function that delegates to the document's validate method.
    
    This is needed for compatibility with code that calls this function directly.
    
    Args:
        doc: Document instance or name
        method: Method name (unused, kept for compatibility)
        
    Returns:
        bool: True if validation succeeded, False otherwise
    """
    try:
        if isinstance(doc, str):
            doc = frappe.get_doc("BPJS Payment Summary", doc)

        # Store company abbreviation for use throughout the document
        if hasattr(doc, "company") and doc.company:
            doc._company_abbr = frappe.get_cached_value("Company", doc.company, "abbr")

        # Ensure we have a document instance with a validate method
        if hasattr(doc, "validate") and callable(doc.validate):
            doc.validate()
            return True
        else:
            frappe.log_error(
                "Invalid document passed to validate function",
                "BPJS Payment Summary Validation Error"
            )
            return False
    except Exception as e:
        logger.error(f"Error in BPJS Payment Summary validation: {str(e)}")
        frappe.log_error(
            f"Error in BPJS Payment Summary validation: {str(e)}\n\n"
            f"Traceback: {frappe.get_traceback()}",
            "BPJS Payment Summary Validation Error"
        )
        return False
