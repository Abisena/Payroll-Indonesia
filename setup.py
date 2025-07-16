# setup.py yang dikoreksi
from setuptools import setup, find_packages
import os

version = '0.1.0'

setup(
    name="payroll_indonesia",
    version=version,
    description="Payroll module for Indonesian companies",
    author="PT. Innovasi Terbaik Bangsa",
    author_email="danny.a.pratama@cao-group.co.id",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=["frappe"]
)
