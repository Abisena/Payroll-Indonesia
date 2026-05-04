# payroll_indonesia/setup/salary_component_accounts.py
"""
Auto-set account mapping untuk Salary Component per company.
Dijalankan setiap after_migrate supaya tidak hilang saat deploy.
"""

import frappe


ACCOUNT_MAPPING = {
    "Tiga Perkasa Teknik": {
        "BPJS Kesehatan Employee": "2131011 - Accrued Expense Health Insurance/BPJS - TPT",
        "BPJS JHT Employee": "2131014 - Accrued Payable BPJS JHT - TPT",
        "BPJS JP Employee": "2131015 - Accrued Payable BPJS JP - TPT",
    }
}


def sync_salary_component_accounts():
    """Sync account mapping untuk semua company yang terdaftar."""
    for company, components in ACCOUNT_MAPPING.items():
        # Skip kalau company tidak ada di site ini
        if not frappe.db.exists("Company", company):
            continue

        for component_name, account in components.items():
            # Skip kalau salary component tidak ada
            if not frappe.db.exists("Salary Component", component_name):
                continue

            # Skip kalau account tidak ada
            if not frappe.db.exists("Account", account):
                frappe.logger("payroll_indonesia").warning(
                    f"Account {account} tidak ada di site ini, skip {component_name}"
                )
                continue

            doc = frappe.get_doc("Salary Component", component_name)

            # Cek apakah sudah ada mapping untuk company ini
            existing = [a for a in doc.accounts if a.company == company]
            if existing:
                # Sudah ada mapping, skip — biarkan user yang setting manual
                continue

            # Tambah mapping baru
            doc.append("accounts", {
                "company": company,
                "account": account
            })
            doc.flags.ignore_links = True
            doc.flags.ignore_permissions = True
            doc.save()
            print(f"✓ Added: {component_name} ({company}) → {account}")

    frappe.db.commit()
