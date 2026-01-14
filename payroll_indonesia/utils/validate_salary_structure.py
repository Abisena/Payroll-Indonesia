def validate_salary_structure_required_components(doc, method):
    import frappe
    
    earning_names = [e.salary_component for e in getattr(doc, "earnings", [])]
    deduction_names = [d.salary_component for d in getattr(doc, "deductions", [])]
    
    missing_components = []
    
    # Validasi BPJS Kesehatan
    if "BPJS Kesehatan Employer" in earning_names or "BPJS Kesehatan Employee" in deduction_names:
        if "BPJS Kesehatan Employer" not in earning_names:
            missing_components.append("BPJS Kesehatan Employer")
        if "BPJS Kesehatan Employee" not in deduction_names:
            missing_components.append("BPJS Kesehatan Employee")
    
    # Validasi BPJS JHT
    if "BPJS JHT Employer" in earning_names or "BPJS JHT Employee" in deduction_names:
        if "BPJS JHT Employer" not in earning_names:
            missing_components.append("BPJS JHT Employer")
        if "BPJS JHT Employee" not in deduction_names:
            missing_components.append("BPJS JHT Employee")
    
    # Validasi BPJS JP
    if "BPJS JP Employer" in earning_names or "BPJS JP Employee" in deduction_names:
        if "BPJS JP Employer" not in earning_names:
            missing_components.append("BPJS JP Employer")
        if "BPJS JP Employee" not in deduction_names:
            missing_components.append("BPJS JP Employee")
    
    # BPJS JKK dan JKM tidak perlu validasi karena tidak ada Employee component
    
    # Validasi PPh 21 - hanya jika ada komponen taxable
    has_taxable = any(
        e.salary_component for e in getattr(doc, "earnings", [])
    )
    if has_taxable:
        if "Biaya Jabatan" not in deduction_names:
            missing_components.append("Biaya Jabatan")
        if "PPh 21" not in deduction_names:
            missing_components.append("PPh 21")
    
    if missing_components:
        frappe.throw(
            "Salary Structure tidak lengkap. Komponen berikut wajib ada:\n- "
            + "\n- ".join(missing_components)
        )
