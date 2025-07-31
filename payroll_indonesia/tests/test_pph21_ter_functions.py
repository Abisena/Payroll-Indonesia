import sys
import os
import types
import importlib

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Minimal frappe stub
frappe = types.ModuleType("frappe")
utils_mod = types.ModuleType("frappe.utils")


def flt(val, precision=None):
    return float(val)


utils_mod.flt = flt


class ValidationError(Exception):
    pass


class DummyLogger:
    def info(self, msg):
        pass

    def warning(self, msg):
        pass


def logger():
    return DummyLogger()


frappe.utils = utils_mod
frappe.logger = logger
frappe.ValidationError = ValidationError

sys.modules.setdefault("frappe", frappe)
sys.modules.setdefault("frappe.utils", utils_mod)

# Import modules after stubbing frappe
pph21_ter = importlib.import_module("payroll_indonesia.config.pph21_ter")
pph21_ter_december = importlib.import_module("payroll_indonesia.config.pph21_ter_december")

import pytest


@pytest.mark.parametrize(
    "ter_code,ptkp_m,bruto,pengurang,bj,rate,expected",
    [
        ("A", 4_500_000, 12_000_000, 480_000, 500_000, 5, 575_000),
        ("B", 3_000_000, 15_000_000, 1_000_000, 1_000_000, 10, 1_400_000),
        ("C", 5_000_000, 20_000_000, 2_000_000, 1_000_000, 15, 2_850_000),
    ],
)
def test_calculate_pph21_TER(monkeypatch, ter_code, ptkp_m, bruto, pengurang, bj, rate, expected):
    monkeypatch.setattr(pph21_ter, "get_ptkp_amount", lambda emp: ptkp_m * 12, raising=False)
    monkeypatch.setattr(pph21_ter, "get_ter_code", lambda emp: ter_code, raising=False)
    monkeypatch.setattr(pph21_ter, "get_ter_rate", lambda code, pkp: rate, raising=False)

    employee = {"employment_type": "Full-time", "tax_status": "TK/0"}
    slip = {
        "earnings": [
            {
                "amount": bruto,
                "is_tax_applicable": 1,
                "do_not_include_in_total": 0,
                "statistical_component": 0,
                "exempted_from_income_tax": 0,
            }
        ],
        "deductions": [
            {
                "salary_component": "BPJS",
                "amount": pengurang,
                "is_income_tax_component": 1,
                "do_not_include_in_total": 0,
                "statistical_component": 0,
            },
            {
                "salary_component": "Biaya Jabatan",
                "amount": bj,
                "is_income_tax_component": 1,
                "do_not_include_in_total": 0,
                "statistical_component": 0,
            },
        ],
    }

    result = pph21_ter.calculate_pph21_TER(employee, slip)
    assert result["pph21"] == expected


def test_calculate_pph21_TER_december(monkeypatch):
    monkeypatch.setattr(pph21_ter_december, "get_ptkp_amount", lambda emp: 54_000_000)
    monkeypatch.setattr(pph21_ter_december.config, "get_value", lambda *args, **kwargs: None)

    slip = {
        "earnings": [
            {
                "amount": 12_000_000,
                "is_tax_applicable": 1,
                "do_not_include_in_total": 0,
                "statistical_component": 0,
                "exempted_from_income_tax": 0,
            }
        ],
        "deductions": [
            {
                "salary_component": "BPJS",
                "amount": 480_000,
                "is_income_tax_component": 1,
                "do_not_include_in_total": 0,
                "statistical_component": 0,
            },
            {
                "salary_component": "Biaya Jabatan",
                "amount": 500_000,
                "is_income_tax_component": 1,
                "do_not_include_in_total": 0,
                "statistical_component": 0,
            },
        ],
    }

    slips = [slip] * 12
    employee = {"employment_type": "Full-time", "tax_status": "TK/0"}
    result = pph21_ter_december.calculate_pph21_TER_december(employee, slips, 0)

    assert result["pkp_annual"] == 78_240_000
    assert result["pph21_annual"] == 5_736_000
    assert result["pph21_month"] == 5_736_000


def test_biaya_jabatan_cap_setting_used(monkeypatch):
    monkeypatch.setattr(pph21_ter, "get_ptkp_amount", lambda emp: 0, raising=False)
    monkeypatch.setattr(pph21_ter, "get_ter_code", lambda emp: "A", raising=False)
    monkeypatch.setattr(pph21_ter, "get_ter_rate", lambda code, pkp: 5, raising=False)

    def fake_get_value(field, default=None):
        if field == "biaya_jabatan_cap":
            return 12_000_000
        if field == "biaya_jabatan_rate":
            return 5
        return default

    import payroll_indonesia.config.config as cfg
    monkeypatch.setattr(cfg, "get_value", fake_get_value)

    employee = {"employment_type": "Full-time", "tax_status": "TK/0"}
    slip = {
        "earnings": [
            {
                "amount": 30_000_000,
                "is_tax_applicable": 1,
                "do_not_include_in_total": 0,
                "statistical_component": 0,
                "exempted_from_income_tax": 0,
            }
        ],
        "deductions": [],
    }

    result = pph21_ter.calculate_pph21_TER(employee, slip)

    assert result["biaya_jabatan"] == 1_000_000
    assert result["pph21"] == 1_450_000
