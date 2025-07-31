# Payroll Indonesia

Modul Payroll Indonesia adalah solusi penggajian untuk ERPNext yang mengikuti regulasi perpajakan dan ketenagakerjaan Indonesia, termasuk PPh 21, BPJS, PTKP, dan metode TER. Modul ini menyediakan salary structure, mapping akun otomatis, serta dokumentasi pengaturan dan perpajakan.

---

## Fitur Utama

- **Salary Component & Structure**  
  Tersedia daftar komponen gaji siap pakai (Basic Salary, Tunjangan, BPJS, Biaya Jabatan, PPh 21, dsb.) yang diatur melalui file fixture dan dapat dimapping ke akun GL.

- **Payroll Settings Dinamis**  
  Semua konfigurasi penggajian (metode perhitungan, BPJS, PTKP, TER, Biaya Jabatan, dsb.) dikelola terpusat di `Payroll Indonesia Settings`.

- **Mapping Akun Otomatis**  
  Komponen gaji otomatis terhubung dengan akun GL sesuai struktur perusahaan, memudahkan proses posting jurnal.

- **Dokumentasi Perpajakan Terbaru**  
  Mendukung aturan PMK 168/2023 dan PMK 66/2023 terkait PPh 21 dan perlakuan natura, serta penjelasan detail perhitungan bulanan dan tahunan.

---

## Struktur Pengaturan

Lihat [docs/payroll_indonesia_settings.md](docs/payroll_indonesia_settings.md) untuk detail pengaturan, termasuk:

- Metode PPh 21 (`TER` dan `Progresif`)
- BPJS rate/cap untuk perusahaan & karyawan
- Tabel PTKP & TER Mapping
- Tabel TER Bracket
- Payroll Options (fallback income tax slab)
- Formula helper untuk Salary Component
- Opsi [Run Payroll Indonesia](docs/payroll_indonesia_settings.md#8-run-payroll-indonesia) & "Run Payroll Indonesia December"

---

## Mapping Salary Component & Akun

Daftar lengkap komponen gaji dan mapping akun dapat dilihat di [docs/salary_component_mapping.md](docs/salary_component_mapping.md).

---

## Dokumentasi Perpajakan

Referensi dan contoh hitung PPh 21, BPJS, serta perlakuan natura (PMK 168 & PMK 66/2023) tersedia di [docs/perpajakan_payroll_indonesia.md](docs/perpajakan_payroll_indonesia.md).
Penjelasan detail flag pajak pada setiap `Salary Component` dapat dibaca di [docs/pajak_pada_salary_component_payroll_indonesia.md](docs/pajak_pada_salary_component_payroll_indonesia.md).

---

## Custom Salary Slip

Penjelasan mengenai kelas `CustomSalarySlip` beserta cara mengaktifkan override terdapat di [docs/custom_salary_slip.md](docs/custom_salary_slip.md).

---

## Instalasi

1. Pastikan ERPNext & Frappe sudah terinstall.
2. Tambahkan Payroll Indonesia ke bench:
   ```
   bench get-app https://github.com/dannyaudian/Payroll-Indonesia.git
   bench install-app payroll_indonesia
   ```
3. Jalankan migrate:
   ```
   bench migrate
   ```
4. Semua komponen, mapping, dan pengaturan akan otomatis terimport dan siap digunakan.
5. Modul akan mencari nama grup akun umum seperti "Expenses" atau "Liabilities" sebagai induk akun payroll. Jika tidak ditemukan, akan digunakan grup akun pertama dengan `root_type` yang sama.
6. Pastikan perusahaan menggunakan **Chart of Accounts** bawaan ERPNext yaitu `Standard Template`. Penggunaan template lain seperti `Standard Indonesia` dapat menyebabkan pembuatan akun GL dari `default_gl_accounts.json` gagal. Apabila parent account yang tercantum di berkas tersebut belum ada, buatlah terlebih dahulu sebelum menjalankan setup.

---

## Lisensi

MIT License

---

## Kontributor

IMOGI - PT. Inovasi Terbaik Bangsa