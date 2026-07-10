# Planning: Employee Modal & Division Page Improvisasi

> Catatan penamaan: kamu sebut `request.html` dan `result.html`, tapi file yang relevan
> berdasarkan screenshot adalah **`employees.html`** (modal edit karyawan) dan
> **`divisions.html`** (struktur divisi). `requests.html`/`results.html` yang ada di repo
> itu untuk flow mutasi SDM & hasil profile matching — tidak relevan ke task ini.
> Plan di bawah pakai nama file yang benar.

---

## Pre-existing blocker (harus difix duluan)

`employees.html` submit pakai `method: 'PUT'`, tapi router cuma punya `@router.patch("/{employee_id}")`.
Update employee **sekarang ini tidak jalan dari UI** (404/405). Semua kerjaan modal baru
percuma kalau ini belum dibenerin dulu.

- Fix: ganti fetch di frontend jadi `PATCH`, atau tambah alias `@router.put` di router.
- Rekomendasi: pakai `PATCH` di frontend (konsisten dengan semantik partial update yang sudah dipakai `EmployeeUpdate`).

---

## Feature 1 — Employee Edit Modal (employees.html)

### Scope
Modal edit berisi: Kode/NIK, Nama, Sub Divisi, Group Divisi (read-only, derived), Latar
Pendidikan, **nilai per kriteria (dinamis sesuai group divisi karyawan)**. Hapus field
Gaji Pokok dari form.

### Data yang dibutuhkan modal
| Field | Sumber | Status |
|---|---|---|
| Kode/NIK, Nama, Posisi | `Employee` | sudah ada |
| Sub Divisi | `Employee.division_id` | sudah ada |
| Group Divisi | `Division.group_id` → `DivisionGroup.name` | **belum di-expose di `EmployeeRead`** |
| Latar Pendidikan | `EducationField` | sudah ada (select), tinggal tampilkan value-nya di edit |
| Nilai per kriteria | `GroupCriteria` (scoped ke `group_id` divisi karyawan) + `EmployeeScore` | endpoint kriteria sudah ada (`GET /api/criteria/division/{id}`), submit nilai **belum ada** |

### Backend changes

1. **`backend/schemas/employee.py`**
   - `EmployeeRead`: tambah `division: DivisionRead` nested (perlu import), atau minimal
     tambah `division_name`, `group_id`, `group_name` sebagai computed fields agar frontend
     tidak perlu extra fetch per row.
   - `EmployeeUpdate`: tambah `scores: Optional[list[EmployeeScoreCreate]] = None`.

2. **`backend/routers/employees.py`** — `update_employee`
   - Saat ini cuma `setattr` field non-score. Perlu tambah logic upsert scores:
     - Kalau `division_id` berubah, validasi ulang bahwa `criteria_id` yang dikirim
       memang milik group criteria dari divisi baru (cegah nilai nyasar ke kriteria
       group lain).
     - Strategi upsert: delete semua `EmployeeScore` existing untuk employee itu, insert
       ulang dari payload (simpel, konsisten dengan `create_employee`). Trade-off: bukan
       true upsert per-row, tapi menghindari state basi (skor kriteria lama yang sudah
       tidak relevan di divisi baru). Revisit kalau ada concurrency issue (>1 admin edit
       bersamaan — saat ini tidak ada locking).
   - Reuse validasi criteria existing dari `create_employee` (extract jadi helper function
     biar tidak duplikat — `_validate_and_persist_scores(db, emp_id, scores)`).

3. **Hapus Gaji Pokok**
   - Jangan drop kolom `base_salary` dari model (breaking migration, dan field ini
     mungkin dipakai modul lain — cek dulu grep sebelum eksekusi). Untuk sekarang: hapus
     dari form UI saja, backend tetap terima default 0.0. Kalau memang mau full removal,
     itu keputusan terpisah (butuh migration + cek semua consumer `base_salary`).

### Frontend changes (`employees.html`)
- Modal edit: tambah section "Penilaian Kriteria" yang di-populate dinamis via
  `GET /api/criteria/division/{division_id}` setiap kali dropdown Sub Divisi berubah
  (bukan cuma saat modal dibuka — supaya kalau user pindah divisi, form kriteria ikut
  refresh).
- Render input angka per kriteria (0–5, sesuai constraint `EmployeeScore.score` /
  `EmployeeScoreBase` di schema), prefill dari `EmployeeRead.scores` kalau edit mode.
- Tampilkan Group Divisi sebagai teks read-only (bukan input), ambil dari
  `division.group_name` (field baru dari schema).
- Hapus input `emp_salary` dari form + payload submit.
- Ganti `method: 'PUT'` → `'PATCH'`.

### ⚠️ BLOCKER — Gaji Pokok full removal konflik dengan Gate 1 (Budget Gate)

`Employee.base_salary` dipakai langsung di `backend/services/sdm_service.py`
(`create_sdm_request`) untuk menghitung `current_expenses`, `company_avg_salary`, dan
validasi `total_projected_expense` vs `Division.monthly_budget` — ini Gate 1 dari alur
mutasi SDM (lihat docstring service: "Gate 1: Budget Evaluated here"). Full removal =
Gate 1 tidak bisa jalan.

### ✅ RESOLVED — Gaji Pokok: Opsi B + Gate 1 auto-pass

Keputusan: sembunyikan `base_salary` dari UI karyawan (opsi B, kolom tetap ada di
model — tidak migration), **dan** Gate 1 budget check di alur mutasi SDM diubah jadi
selalu lolos (tidak lagi mempertimbangkan finansial), sesuai feedback stakeholder yang
tidak mau ada pertimbangan finansial di level divisi.

**Scope perubahan:**

- `frontend/templates/employees.html` — hapus input `emp_salary` dari form + payload
  submit (sama seperti rencana awal opsi B).
- `backend/services/sdm_service.py` (`create_sdm_request`) — ganti blok Gate 1:
  hapus perhitungan `current_expenses`, `company_avg_salary`,
  `projected_additional_cost`, `total_projected_expense`, dan kondisi
  `if target_div.monthly_budget > 0 and total_projected_expense > target_div.monthly_budget`.
  Ganti jadi selalu `budget_gate = GateStatus.passed` dengan `budget_notes` yang jelas
  menyatakan gate ini dinonaktifkan by design (bukan "kebetulan lolos") — supaya kalau
  ada yang baca log/report nanti, jelas ini disengaja, bukan bug. Field
  `budget_gate_status`/`budget_notes` di `SDMRequest` **tetap dipertahankan** di schema
  (biar histori data lama & struktur report tidak berubah), cuma isinya sekarang
  konstan.
- `Employee.base_salary` kolom **tidak dihapus** dari model (sesuai opsi B) — tapi
  sekarang jadi effectively dead data (tidak dibaca logic manapun lagi setelah Gate 1
  diubah). Boleh dibiarkan untuk kompatibilitas/future use, tapi kasih komentar di model
  kalau field ini sudah tidak dipakai perhitungan apapun, biar developer lain (atau kamu
  sendiri 3 bulan lagi) tidak bingung.
- `seed.py` — boleh tetap generate `base_salary` random (tidak ganggu apa-apa karena
  sudah tidak dipakai), atau dihapus dari seed kalau mau bersih-bersih. Tidak wajib.

**Pertanyaan turunan yang perlu kamu konfirmasi juga:** `Division.monthly_budget` masih
ada di form `divisions.html` (field "Anggaran Maksimal"). Kalau finansial memang tidak
mau dilibatkan sama sekali di level divisi, field ini juga jadi tidak relevan (dead
input, tidak divalidasi ke apapun lagi setelah Gate 1 auto-pass).

✅ **Konfirmed: disembunyikan juga.** Tambahan scope:
- `frontend/templates/divisions.html` — hapus input `div_budget` dari modal tambah/edit
  divisi + hapus dari payload submit, dan hapus kolom "ANGGARAN BULANAN" dari tabel list.
- Kolom `Division.monthly_budget` **tidak dihapus** dari model (konsisten dengan opsi B
  untuk `base_salary` — hide UI saja, tidak migration), tapi kasih catatan yang sama:
  field ini sekarang dead data, tidak dibaca logic manapun.
- Cek dulu apakah `div_budget`/`monthly_budget` dipakai di tempat lain selain
  `sdm_service.py` (misal laporan/dashboard) sebelum eksekusi — **sudah dicek**: cuma
  ada di `divisions.html` (form+tabel), `sdm_service.py` (Gate 1), dan
  `seed.py`/model/schema. Tidak ada dependency tersembunyi di modul lain. Aman untuk
  di-hide.

---

## Feature 2 — Division Page Restructure (divisions.html)

### Scope
Split jadi 2 bagian:
1. **Atas (existing, reorganisasi)** — Group Divisi sebagai container, di dalamnya
   sub-divisi bisa ditambah. Dipakai untuk kriteria (flow "Bobot" yang sudah ada, tetap
   dipakai, cuma dipindah konteksnya jadi per-group).
2. **Bawah (baru)** — Box per sub-divisi yang bisa diisi/assign karyawan.

### Masalah existing yang harus dibenerin dulu
- Tabel sekarang nampilin `<span>ID: {group_id}</span>` mentah (lihat screenshot) —
  bukan nama group. Data-nya sudah ada di `loadGroupsDropdown()` (fetch
  `/api/divisions/groups`), tinggal bikin `Map(id -> name)` dan pakai buat render, tidak
  perlu ubah backend.

### Backend changes
- Tidak perlu endpoint baru untuk restrukturisasi tampilan (group name lookup bisa
  full di-handle client-side dari data yang sudah di-fetch).
- **Assign karyawan ke sub-divisi** dari box bawah: reuse
  `PATCH /api/employees/{id}` (payload `{division_id}`) — tidak perlu endpoint baru,
  asal Feature 1's fix (PATCH bug) sudah selesai.
- **Jumlah total bagian per group**: hitung di frontend dari response
  `GET /api/divisions/?group_id=X` (`.length`), tidak perlu agregat endpoint baru — cukup
  murah untuk skala data ini (belasan divisi).
- **Total WLA per Group Divisi** (bagian atas, level group): agregasi dari semua
  divisi (sub-bagian) di dalam group itu. Karena skala data kecil (per group cuma
  berisi beberapa sub-divisi), cukup fetch `GET /api/wla/division/{id}/latest` untuk
  tiap divisi anggota group lalu sum client-side — tidak perlu endpoint agregat baru
  dulu (YAGNI, revisit kalau jumlah divisi per group membesar signifikan). Definisi
  metrik "total" = sum `total_workload_hours` dan sum `headcount` across divisi anggota
  (bukan average `wla_value`, karena `wla_value` per divisi punya basis capacity
  berbeda-beda — sum-of-raw-hours lebih valid daripada rata-rata rasio). **Konfirmasi
  ke aku kalau definisi ini bukan yang kamu maksud.**
- **WLA per sub-divisi** (bagian bawah, box per divisi): **PENDING** — ditunda sampai
  kamu dapat kejelasan dari user/stakeholder. Endpoint backend (`/api/wla/division/{id}/latest`)
  sudah siap dipakai kapan saja begitu requirement-nya jelas, jadi tidak ada extra kerjaan
  backend untuk ini nanti.

### Frontend changes (`divisions.html`)
- Restructure render loop: group by `group_id` dulu (dari `/api/divisions/groups` +
  `/api/divisions/`), baru render card per group berisi list sub-divisi di dalamnya
  (ganti dari flat table).
- Section bawah baru: per sub-divisi, tampilkan box dengan:
  - List karyawan aktif di divisi itu (`GET /api/employees/?division_id=X`)
  - Search/select karyawan lain (semua employee) + tombol "Pindahkan ke sini" →
    `PATCH /api/employees/{id}` dengan `division_id` baru.
  - **Konfirmed**: box ini khusus untuk penempatan awal (karyawan baru / belum pernah
    dimutasi), bukan pengganti flow mutasi resmi. Pemindahan karena hasil mutasi tetap
    lewat `SDMRequest` → `TransferLetter` yang sudah ada (Gate A/B, WLA check di
    `simulate_rotation` tetap utuh, tidak disentuh).
  - Perlu guard biar box ini tidak disalahgunakan buat mutasi rutin: tampilkan warning
    text di UI ("Gunakan hanya untuk penempatan awal — mutasi resmi lewat menu Pengajuan
    Mutasi SDM"). Opsional (bisa nyusul, bukan blocker): filter list "karyawan lain" di
    box ini supaya hanya nampilin karyawan yang belum pernah punya `TransferLetter`
    (baru/belum termutasi) — kalau mau, cek dulu relasi `TransferLetter` ke `Employee` di
    `models.py` dulu, belum aku cek detailnya.

### Dead code catatan
- `frontend/modals/modal-division.html` sudah ada modal tab Divisi/Group terpisah yang
  sepertinya **tidak dipakai** oleh `divisions.html` (yang punya inline modal sendiri).
  Cek dulu apakah ini dipakai halaman lain sebelum nulis ulang — kalau tidak, ini
  duplikasi yang perlu diputuskan: pakai yang mana, hapus yang lain.

---

## Ringkasan file yang kena dampak

| File | Perubahan |
|---|---|
| `backend/schemas/employee.py` | nested division/group, scores di update |
| `backend/routers/employees.py` | fix PATCH bug, upsert scores logic |
| `frontend/templates/employees.html` | dynamic criteria form, hapus gaji, fix method |
| `frontend/templates/divisions.html` | restructure jadi grouped, box assign karyawan |
| `frontend/modals/modal-division.html` | audit — dipakai atau dead code? |

## Status keputusan
1. ✅ Assign karyawan (box bawah) — untuk penempatan awal/karyawan baru, bukan pengganti
   flow mutasi resmi. Flow mutasi (`SDMRequest`/Gate A/B) tidak diubah.
2. ✅ "Total WLA" — level Group Divisi (sum across sub-divisi anggota). WLA per
   sub-divisi individual: **pending**, tunggu kejelasan dari stakeholder kamu.
3. ✅ Gaji Pokok — opsi B (hide dari UI, kolom tetap di model) + Gate 1 budget check di
   `sdm_service.py` diubah jadi auto-pass (finansial tidak lagi dilibatkan di evaluasi
   mutasi divisi). `Division.monthly_budget` juga disembunyikan dari form
   `divisions.html`, konsisten dengan keputusan ini — sudah dicek, tidak ada dependency
   tersembunyi di modul lain.

## Urutan pengerjaan disarankan
1. Fix PATCH/PUT bug (blocker, kecil, 5 menit)
2. Gate 1 auto-pass + hide `emp_salary` dari form employees.html (sudah jelas scope-nya,
   bisa dikerjakan duluan, tidak depend ke fitur lain)
3. Nested schema (division/group di EmployeeRead) — dasar buat kedua fitur
4. Feature 1 (employee modal + dynamic scores per kriteria)
5. Feature 2 top section (group name fix, restructure per group, total WLA per group)
6. Feature 2 bottom section (assign box, dengan warning text "khusus penempatan awal")
