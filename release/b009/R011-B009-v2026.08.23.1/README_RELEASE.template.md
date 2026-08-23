# Statistika Berbasis Data - rilis pelestarian R011-B009

Versi: `2026.08.23.1-R011-B009`

Status: **edisi kerja yang belum lengkap**. Rilis ini mempertahankan batas B009 setelah sumber, build deterministik, pemeriksaan struktur, pemeriksaan visual, backend modular, dan penerimaan terminal seluruhnya lulus. Rilis ini bukan edisi Bahasa Indonesia lengkap.

## Cakupan yang diterjemahkan dan diterima

- pembuka Bab 3 dan bagian *Defining probability* / *Peluang* sampai subseksi *Independence*;
- 18 latihan terpandu dan 18 jawaban publik inline yang menyertainya;
- 12 latihan EoCE pada berkas `defining_probability.tex`;
- jawaban publik ganjil EoCE 1, 3, 5, 7, 9, dan 11;
- catatan celah umpan balik `O001` untuk jawaban 2, 4, 6, 8, 10, dan 12.

Materi setelah penanda batas B009, termasuk *Conditional probability* dan bagian berikutnya, tetap berupa saksi sumber berbahasa Inggris dalam PDF lengkap agar build dapat direproduksi; sufiks tersebut bukan hasil terjemahan yang diterima. Tidak ada solusi instruktur terbatas yang diakses, direkonstruksi, atau dinyatakan sebagai solusi sumber.

## Berkas

1. `00_STATISTIKA_BERBASIS_DATA_ID_R011-B009_WORKING_READER.pdf` - PDF pembaca utama; urutan berkas sengaja mendahulukan pembaca.
2. `01_STATISTIKA_BERBASIS_DATA_ID_R011-B009_EDITABLE_SOURCE.zip` - penutupan sumber LaTeX dan aset yang dapat disunting, dengan pengecualian hak komponen yang dicatat.
3. `02_STATISTIKA_BERBASIS_DATA_ID_R011-B009_MODULAR_BACKEND.zip` - ekspor backend modular B009, manifes, skema, dan tanda terima QA.
4. `CITATION.cff`, `LICENSES_AND_ATTRIBUTION.md`, `README_RELEASE.md`, `RELEASE_MANIFEST.json`, `SHA256SUMS.txt`, dan `ZENODO_METADATA.json` - metadata, hak, inventaris, dan checksum.

`RELEASE_MANIFEST.json` mengikat byte sumber B009, PDF deterministik, audit visual, tanda terima batas, backend yang diterima, dan verifikasi pascapenerimaan. Pembuatan paket menolak berjalan sebelum semua identitas terminal tersedia dan cocok.

## Otoritas dan kredit

Karya ini merupakan turunan Bahasa Indonesia dari *OpenIntro Statistics*, Edisi Keempat, oleh David M. Diez, Mine Çetinkaya-Rundel, dan Christopher D. Barr. Sumber resmi dibekukan pada komit `fee25091fb24e89c36296fd67c48c1fcf7a93b6e` dan pohon `d61cc601e7d97759ce805900520f784d02a0489e`.

Judul turunan: *Statistika Berbasis Data*. Karya ini bukan produk OpenIntro serta tidak berafiliasi dengan atau didukung oleh OpenIntro. Kontributor edisi Bahasa Indonesia: Codex, atas permintaan pengguna.

Identifikasi model produksi: **OpenAI Codex gpt-5.6-sol, Ultra**. Identifikasi alat ini tidak menggantikan atau mengurangi kredit penulis sumber dan kontributor manusia.

## Terminologi dan QA

QA terminologi satu kali membandingkan istilah terhadap sumber Indonesia yang diidentifikasi dalam receipt `R011_B009_TERMINOLOGY_EVIDENCE_RECEIPT.json`. Keputusan B009 mempertahankan `probabilitas` untuk disiplin/bab dan `peluang` untuk kesempatan/peristiwa individual, bersama `peristiwa`, `saling lepas`, `ruang sampel`, `komplemen`, `independen`, dan `Aturan Perkalian`; tidak ada koreksi baru yang diperlukan.

## Lisensi dan keterbatasan

Selain komponen yang dinyatakan terpisah, teks sumber dan terjemahan tersedia berdasarkan **CC BY-SA 3.0 Unported**. Hak berkas individual, data, kode, foto, dan dependensi tetap mengikuti manifes hak komponen; hak yang lebih khusus mengesampingkan lisensi teks umum. Foto roulette, producer GPL, dan sumber terminologi internal tidak dilisensikan ulang secara tersirat.

PDF mendeklarasikan bahasa `id-ID`, tetapi belum ditandai secara struktural. Pembaca HTML yang dapat diakses tetap diperlukan sebelum edisi lengkap dapat dinyatakan selesai.

Garis keturunan pelestarian: <https://doi.org/10.5281/zenodo.22059801>.
