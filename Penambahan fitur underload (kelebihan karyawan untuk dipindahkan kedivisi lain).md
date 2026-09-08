# Planning: Modul Sourcing Kandidat Surplus (Overstaffed → Understaffed)

**Proyek:** Rotasi SDM Klinik Pramita
**Target Sprint:** 2 Hari
**Fokus Arsitektur:** Data-Driven Decision Making, Maintainability, Observability, dan UX Transparansi.

---

## 1. Konteks & Keputusan Desain Terkini

### Masalah Awal
Sistem dapat mendeteksi divisi yang mengalami surplus SDM (WLA < 1.0)[cite: 4]. Namun, antarmuka `requests.html` saat ini beroperasi dengan asumsi skenario "kekurangan orang" secara umum, menampilkan semua pegawai secara bebas[cite: 2]. Jika HRD dibiarkan menyeleksi secara manual dari populasi acak saat menangani divisi surplus, hal ini membuka celah anomali operasional dan ketidakseimbangan beban kerja di divisi lain yang stabil.

### Keputusan Arsitektural (Redesign)
1.  **Tanpa Entitas Baru:** Modul ini bertindak sebagai jembatan *sourcing* dari divisi surplus menuju *pipeline* eksisting (Gate A, Gate B, dan Gate 2 WLA)[cite: 2].
2.  **Penghapusan Kerapuhan Klien (SessionStorage):** Rencana awal menggunakan `sessionStorage` dibatalkan karena rentan hilang dan tidak dapat dibagikan (non-shareable)[cite: 2]. Sistem akan menggunakan parameter URL persisten (`?donor_division=ID`) untuk mempertahankan *state*.
3.  **Pemfilteran Absolut:** Untuk memastikan integritas keputusan operasional, jika alur diinisiasi dari peringatan surplus, HRD **hanya** diizinkan memilih kandidat dari divisi donor tersebut[cite: 2].
4.  **Transparansi Sistem (Prioritas Naik):** Kandidat yang tereliminasi oleh Gate 2 (kalkulasi WLA) wajib ditampilkan alasannya di `results.html`, tidak boleh dihilangkan dari antarmuka secara diam-diam[cite: 2].

---

## 2. Alur Sistem (End-to-End Workflow)

| Fase | Aksi Sistem / Pengguna | Komponen Terlibat |
| :--- | :--- | :--- |
| **1. Deteksi** | WLA mendeteksi rasio < 1.0. Lencana peringatan "SURPLUS" muncul di dasbor. | `wla_service.py`, `wla.html`[cite: 4] |
| **2. Inisiasi** | HRD mengklik lencana surplus. Sistem melakukan *redirect* persisten. | `wla.html` → `/requests?donor_division=ID` |
| **3. Sourcing** | Sistem membaca parameter URL dan mengunci *query* pencarian pegawai secara absolut pada ID divisi donor tersebut. | `requests.html`, `employees.py` |
| **4. Seleksi** | HRD memilih kandidat dari *pool* yang sudah disaring. | `requests.html` (Modal Kandidat)[cite: 2] |
| **5. Proses Gate** | Kandidat melewati evaluasi Gate A (Administrasi) dan Gate B (Wawancara). | `sdm_service.py`[cite: 2] |
| **6. WLA Stress-Test**| *Profile Matching* berjalan; Gate 2 mensimulasikan penarikan kandidat. Sistem memastikan penarikan ini aman. | `run_matching()`, `wla_service.py`[cite: 2, 4] |
| **7. Finalisasi** | Halaman hasil menampilkan peringkat. Kandidat yang ditolak Gate 2 tetap tampil dengan catatan log eliminasi yang transparan. | `results.html`, `sdm_service.py`[cite: 2] |

---

## 3. Rencana Eksekusi Sprint (2 Hari)

### Hari 1: Kesiapan Backend & Keamanan API
Fokus pada penyediaan data yang presisi dan menjaga *Backwards Compatibility*.

*   **Task 1.1:** Implementasi fungsi `get_active_overstaffed_divisions()` di `wla_service.py` untuk mengiterasi data divisi dan mengekstrak status surplus pada periode terbaru[cite: 4].
*   **Task 1.2:** Pembuatan *endpoint* `GET /api/wla/overstaffed` di `backend/routers/wla.py` dengan proteksi RBAC (hanya HRD & Super Admin)[cite: 3].
*   **Task 1.3:** Modifikasi `GET /api/employees/` di `backend/routers/employees.py` untuk menerima kueri `?division_id=X`. Pastikan parameter diatur sebagai `Optional` agar tidak merusak fungsi halaman lain[cite: 2].
*   **Task 1.4:** Unit Testing manual via terminal/Postman untuk memvalidasi *output* data dari dua *endpoint* di atas.

### Hari 2: Restriksi Frontend & Visibilitas Data
Fokus pada pencegahan kesalahan pengguna (UX) dan transparansi algoritma (Observability).

*   **Task 2.1:** Modifikasi tombol lencana di `wla.html` untuk memicu tautan dengan format *URL params* (`/requests?donor_division=X`)[cite: 2].
*   **Task 2.2:** Pembaruan logika JavaScript di `requests.html` pada fungsi `bukaModalKandidat()`. Jika parameter URL terdeteksi, kunci API *call* ke divisi terkait dan tampilkan *banner* peringatan visual "Mode Sourcing Surplus Aktif". Kunci elemen antarmuka agar HRD tidak bisa mengganti filter divisi secara manual[cite: 2].
*   **Task 2.3 (Penyelesaian Backlog Kritis):** Refaktor `results.html` dan manipulasi *response* JSON dari `run_matching()` agar mengikutsertakan kandidat gagal Gate 2. Tambahkan komponen visual (misal: baris berwarna abu-abu/merah pudar) dengan penjelasan eksplisit dari *WLA Check warning*[cite: 2].
*   **Task 2.4:** Pengujian regresi (Regression Testing). Pastikan pembuatan pengajuan rotasi reguler (tanpa parameter surplus) tetap beroperasi normal dan menampilkan seluruh pegawai[cite: 2].

---

## 4. Acceptance Criteria (Checklist Kualitas)

- [ ] *Endpoint* `/api/employees/` tidak menyebabkan *error 500* atau *422* saat dipanggil tanpa parameter `division_id`.
- [ ] Pengaksesan lencana di Dasbor WLA tidak lagi menggunakan `sessionStorage` atau `localStorage`, murni mengandalkan interpretasi *Query Parameter*.
- [ ] Dalam "Mode Sourcing Surplus", antarmuka pencarian kandidat tidak memungkinkan HRD melakukan injeksi modifikasi divisi lain.
- [ ] Kandidat yang digagalkan oleh Gate 2 (WLA Check) secara absolut muncul di `results.html` dengan keterangan *error* yang dapat dibaca manusia (Human-Readable Error).
- [ ] Alur reguler untuk divisi defisit tidak terpengaruh secara struktural maupun performa.