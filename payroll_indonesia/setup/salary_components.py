import frappe

def setup_allowance_components():
    """Setup formula untuk Tunjangan Makan & Transport"""
    
    components = [
        {
            "salary_component": "Tunjangan Makan",
            "salary_component_abbr": "TM",
            "type": "Earning",
            "description": "Tunjangan makan per hari × jumlah hari hadir",
            "depends_on_payment_days": 0,
            "amount_based_on_formula": 1,
            "formula": "(meal_allowance / total_working_days) * payment_days if total_working_days else meal_allowance",
            "is_tax_applicable": 1,
            "round_to_the_nearest_integer": 1,
            "exempted_from_income_tax": 0
        },
        {
            "salary_component": "Tunjangan Transport",
            "salary_component_abbr": "TT",
            "type": "Earning",
            "description": "Tunjangan transport bulanan (prorate payment days)",
            "depends_on_payment_days": 0,
            "amount_based_on_formula": 1,
            "formula": "(transport_allowance / total_working_days) * payment_days if total_working_days else transport_allowance",
            "is_tax_applicable": 1,
            "round_to_the_nearest_integer": 1,
            "exempted_from_income_tax": 0,
        },
        {
            "salary_component": "Tunjangan Operational",
            "salary_component_abbr": "Opr_1",
            "type": "Earning",
            "description": "Tunjangan operational bulanan dari SSA (prorate payment days)",
            "depends_on_payment_days": 0,
            "amount_based_on_formula": 1,
            "formula": "(tunjangan_operational / total_working_days) * payment_days if total_working_days else tunjangan_operational",
            "is_tax_applicable": 1,
            "round_to_the_nearest_integer": 1,
            "exempted_from_income_tax": 0,
        },
    ]
    
    for comp_data in components:
        # Cek apakah sudah ada
        if frappe.db.exists("Salary Component", comp_data["salary_component"]):
            # Update existing
            doc = frappe.get_doc("Salary Component", comp_data["salary_component"])
            doc.update(comp_data)
            doc.flags.ignore_links = True
            doc.save(ignore_permissions=True)
            print(f"✓ Updated: {comp_data['salary_component']}")
        else:
            # Create new
            doc = frappe.get_doc({
                "doctype": "Salary Component",
                **comp_data
            })
            doc.insert(ignore_permissions=True)
            print(f"✓ Created: {comp_data['salary_component']}")
    
    frappe.db.commit()