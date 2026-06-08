# Konfirmasi Implementasi: Profile Matching Berbasis Aturan KPI Organisasi
## Pramita Lab — Dokumen Konfirmasi Stakeholder
**Versi:** 2.0
**Tanggal:** Mei 2026
**Status:** Menunggu Konfirmasi
**Dibuat oleh:** Tim Pengembang Sistem
**Untuk ditinjau oleh:** Kepala HRD, Kepala Cabang, Kepala Laboratorium, Manajemen TI

---

## 1. Tujuan Dokumen

Dokumen ini merangkum hasil diskusi teknis mengenai kelayakan implementasi metode Profile Matching menggunakan aturan penilaian KPI organisasi Pramita Lab, dan meminta konfirmasi final dari stakeholder sebelum implementasi dimulai.

**Kesimpulan utama dari diskusi:** Implementasi ini **layak dan tidak merusak sistem yang sudah ada.** Aturan KPI organisasi kompatibel dengan kerangka Profile Matching sebagai metode pengambilan keputusan.

---

## 2. Apa Yang Sudah Dikonfirmasi Tim Teknis

Berdasarkan diskusi sebelumnya, tiga hal berikut sudah dikonfirmasi dan akan langsung diimplementasi:

| # | Keputusan | Jawaban Terkonfirmasi |
|---|---|---|
| 1 | Ambang batas ">90" mengacu pada apa? | **Nilai N** (rasio pencapaian/target) — N > 0.90 = skor penuh |
| 2 | Indikator "lebih rendah = lebih baik" dihitung bagaimana? | **Sistem otomatis** — jika pencapaian ≤ target → N = 1.0 (sempurna); jika pencapaian > target → N = target/pencapaian |
| 3 | Apakah aturan KPI menggantikan tabel gap? | **Keduanya ada** — HRD memilih metode per divisi |

---

## 3. Bagaimana Sistem Akan Bekerja

### 3.1 Dua Metode Penilaian

Sistem akan memiliki dua mesin penilaian yang berjalan berdampingan. HRD menentukan metode mana yang digunakan untuk setiap divisi.

| Metode | Digunakan Untuk | Input | Cara Kerja |
|---|---|---|---|
| **Tabel Gap** (sudah ada) | Divisi non-klinis | Nilai 1–5 per kriteria | Gap = nilai karyawan − nilai target → dipetakan ke bobot 1.0–5.0 |
| **Aturan KPI 3-Band** (baru) | Divisi klinis / Laboratorium | Data pencapaian aktual per indikator | N = pencapaian/target → band rule → konversi ke skala 1–5 |

### 3.2 Aturan KPI 3-Band

Aturan yang akan diimplementasi sesuai dokumen KPI Pramita Lab:

```
N = pencapaian / target

Jika N > 0.90   → Skor = Bobot penuh
Jika 0.80 ≤ N ≤ 0.90 → Skor = 0.5 × Bobot
Jika N < 0.80   → Skor = 0
```

**Untuk indikator "lebih rendah = lebih baik"** (contoh: Tingkat Ketidaksesuaian, Kejadian Spesimen Hilang):

```
Jika pencapaian ≤ target → N = 1.0 (otomatis nilai sempurna)
Jika pencapaian > target → N = target / pencapaian
```

Penanganan khusus ini menghindari pembagian dengan nol pada kasus target = 0% dan pencapaian = 0%.

### 3.3 Alur Perhitungan Lengkap (Metode KPI)

```
Input data KPI per indikator
(pencapaian, target, bobot, arah indikator)
          ↓
Hitung Nilai N per indikator
          ↓
Terapkan aturan 3-band → Skor per indikator
          ↓
Jumlahkan semua skor → Total KPI (skala 0–100)
          ↓
Konversi ke skala 1–5:
pm_score = (total_KPI / 100) × 4 + 1
          ↓
Profile Matching: NCF dan NSF dihitung
dengan bobot per kriteria
          ↓
Skor Akhir = 0.6 × NCF + 0.4 × NSF
          ↓
Ranking kandidat
```

### 3.4 Contoh Perhitungan (dari dokumen KPI NURUL FITRI)

| Indikator | Pencapaian | Target | N | Band | Bobot | Skor |
|---|---|---|---|---|---|---|
| Index Kepuasan Pelanggan | 95 | 95 | 1.00 | >0.90 | 5 | 5 |
| Turn Around Time | 92.6 | 95 | 0.975 | >0.90 | 5 | 5 |
| On Time Performance | 91.7 | 84 | 1.00* | >0.90 | 10 | 10 |
| Kuantitas pekerjaan analisa | 100 | 100 | 1.00 | >0.90 | 10 | 10 |
| Tingkat ketidaksesuaian spesimen | 0 | 0 | 1.00† | >0.90 | 5 | 5 |
| **Total** | | | | | **100** | **~100** |

*OTP: pencapaian 91.7 > target 84, namun ini indikator "lebih tinggi = lebih baik" dan pencapaian melampaui target → N = 1.0 (capped)
†Indikator lower-is-better: pencapaian 0 ≤ target 0 → N = 1.0 otomatis

**Hasil konversi:** pm_score = (100/100) × 4 + 1 = **5.0** → EXCELLENT → Rank #1 kandidat kuat

### 3.5 Mengapa Tidak Merusak Sistem yang Ada

- Divisi non-klinis (Customer Service, Administrasi, dll.) tetap menggunakan tabel gap — tidak ada perubahan
- Seluruh pipeline setelah perhitungan skor (NCF/NSF, skor akhir, ranking, WLA, surat tugas) tidak berubah
- Gate A dan Gate B (kelayakan pendidikan dan interview) tetap berlaku

---

## 4. Satu Ambiguitas yang Perlu Dikonfirmasi

### 4.1 Turn Around Time — Nilai N Tidak Cocok

Dari dokumen KPI:
- Pencapaian = 92.6, Target = 95
- N yang tercantum di formulir = **0.93**
- N hasil formula pencapaian/target = 92.6/95 = **0.974**

Kedua angka ini berbeda. Kemungkinan penyebab:
- Formula yang digunakan berbeda (bukan pencapaian/target sederhana)
- Ada penyesuaian manual oleh Pejabat Penilai
- Ada faktor koreksi yang tidak tercantum di dokumen

**Dalam kedua kasus, hasilnya tetap masuk band yang sama (>0.90 = skor penuh)**, sehingga tidak mempengaruhi hasil akhir untuk indikator ini. Namun untuk kasus di mana N berada tepat di batas band (misalnya antara 0.89 dan 0.91), perbedaan formula bisa mengubah hasil.

> **[KONFIRMASI A]** Apakah formula N = pencapaian/target sudah benar, atau ada formula lain yang digunakan untuk jenis indikator tertentu?

---

## 5. Pertanyaan Konfirmasi untuk Stakeholder

Selain Konfirmasi A di atas, berikut hal-hal yang masih memerlukan keputusan sebelum implementasi dimulai.

### 5.1 Periode Data KPI

> **[KONFIRMASI B]** Data KPI periode mana yang digunakan untuk penilaian rotasi/mutasi?
>
> - **Opsi 1:** Periode terbaru saja (contoh: Maret 2026)
> - **Opsi 2:** Rata-rata 3 periode terakhir
> - **Opsi 3:** HRD memilih periode yang relevan saat membuat permintaan mutasi

### 5.2 Karyawan Tanpa Data KPI

Tidak semua karyawan mungkin memiliki data KPI yang lengkap (karyawan baru, pindahan, dll.).

> **[KONFIRMASI C]** Jika kandidat tidak memiliki data KPI untuk periode yang dipilih, apa yang terjadi?
>
> - **Opsi 1:** Karyawan otomatis dikeluarkan dari daftar kandidat
> - **Opsi 2:** Karyawan tetap masuk tapi diberi skor minimum (N = 0)
> - **Opsi 3:** HRD dapat menginput nilai manual sebagai pengganti

### 5.3 Struktur KPI Tim vs Individu

Dokumen KPI memiliki dua bagian: **A. Kinerja Tim** dan **B. Kinerja Individu**. Keduanya mempengaruhi total skor.

> **[KONFIRMASI D]** Untuk penilaian mutasi, apakah kedua bagian (Tim dan Individu) digunakan, atau hanya Kinerja Individu?
>
> - **Opsi 1:** Keduanya digunakan (seperti di formulir KPI asli)
> - **Opsi 2:** Hanya Kinerja Individu — kinerja tim tidak relevan untuk penilaian individu
> - **Opsi 3:** Bobot keduanya dapat dikonfigurasi per divisi oleh HRD

### 5.4 Siapa yang Menginput Data KPI ke Sistem

> **[KONFIRMASI E]** Siapa yang bertanggung jawab menginput data pencapaian KPI ke dalam sistem DSS?
>
> - **Opsi 1:** Pejabat Penilai (Supervisor) menginput langsung di sistem
> - **Opsi 2:** HRD menginput berdasarkan formulir KPI yang sudah ditandatangani
> - **Opsi 3:** Data diimpor dari sistem penilaian yang sudah ada (jika ada)

### 5.5 Validasi Skor KPI

> **[KONFIRMASI F]** Apakah skor KPI yang diinput perlu divalidasi/disetujui oleh pihak tertentu sebelum digunakan untuk perhitungan mutasi?
>
> - **Opsi 1:** Tidak perlu — data dari formulir KPI yang sudah ditandatangani dianggap final
> - **Opsi 2:** Perlu persetujuan Kepala Cabang sebelum digunakan
> - **Opsi 3:** Sistem menampilkan warning jika skor berbeda jauh dari periode sebelumnya

---

## 6. Apa yang Akan Dibangun (Setelah Konfirmasi)

### Komponen Baru
- **`KPIIndicator`** — master indikator per divisi (nama, bobot, arah, tipe Tim/Individu)
- **`KPIRecord`** — data pencapaian aktual per karyawan per indikator per periode
- **`KPIPeriod`** — periode penilaian (YYYY-MM)
- **Mesin KPI 3-Band** — fungsi perhitungan N, band rule, konversi 1–5
- **`scoring_method` pada Criteria** — pilihan `gap_table` atau `kpi_band` per divisi

### Tidak Ada yang Dihapus
Semua komponen sistem yang sudah ada tetap berjalan. Tidak ada migrasi data yang merusak.

### Estimasi Kompleksitas
- Perubahan model database: **sedang** (3 tabel baru, 1 kolom baru)
- Perubahan logika bisnis: **rendah-sedang** (engine baru terisolasi)
- Perubahan frontend: **rendah** (form input KPI baru, tampilan hasil tidak berubah)
- Risiko regresi ke fitur yang sudah ada: **sangat rendah**

---

## 7. Format Respons yang Diminta

Mohon berikan konfirmasi untuk setiap poin berikut:

```
[KONFIRMASI A]: ...
[KONFIRMASI B]: Opsi 1 / 2 / 3
[KONFIRMASI C]: Opsi 1 / 2 / 3
[KONFIRMASI D]: Opsi 1 / 2 / 3
[KONFIRMASI E]: Opsi 1 / 2 / 3
[KONFIRMASI F]: Opsi 1 / 2 / 3
```

Setelah semua konfirmasi diterima, implementasi dapat dimulai dalam sprint berikutnya.

---

## 8. Lampiran — Peta Keputusan Sebelumnya

| Dokumen | Tanggal | Keputusan |
|---|---|---|
| Stakeholder Review v1.0 | Mei 2026 | 8 keputusan awal diidentifikasi |
| Diskusi teknis | Mei 2026 | Konfirmasi 3 keputusan: threshold N, lower-is-better, dual method |
| Dokumen ini (v2.0) | Mei 2026 | 6 konfirmasi tersisa sebelum implementasi |

---

*Dokumen ini disiapkan oleh Tim Pengembang Sistem Informasi SDM Pramita Lab.*
*Pertanyaan teknis dapat diarahkan ke tim developer sebelum rapat konfirmasi.*
