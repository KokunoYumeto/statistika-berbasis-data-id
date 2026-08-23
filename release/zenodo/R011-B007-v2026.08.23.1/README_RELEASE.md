# Statistika Berbasis Data - rilis pelestarian R011-B007

Versi: `2026.08.23.1 / R011-B007`

Status: **edisi kerja yang belum lengkap**. Rilis ini mempertahankan batas produksi terakhir yang telah lulus seluruh gerbang penerimaan. Rilis ini bukan edisi Bahasa Indonesia lengkap dan tidak boleh digambarkan sebagai edisi lengkap.

## Cakupan yang telah diterjemahkan dan diterima

- halaman judul, atribusi, dan materi pendahuluan turunan;
- Bab 1 lengkap, termasuk Bagian 1.1-1.4, latihan akhir bab 1.35-1.44, dan semua jawaban publik yang tersedia dari sumber;
- pembuka Bab 2 dan Bagian 2.1, *Menelaah data numerik*;
- Bagian 2.2, *Menelaah data kategoris*;
- Bagian 2.3, *Studi kasus: vaksin malaria*, termasuk latihan 2.25-2.26;
- semua jawaban publik yang tersedia sampai latihan 2.25;
- celah umpan balik untuk latihan tanpa jawaban publik dicatat sebagai `O001`; tidak ada solusi instruktur terbatas yang diakses, direkonstruksi, atau diciptakan seolah-olah berasal dari sumber.

PDF batas kerja tetap memuat latihan tinjauan Bab 2 mulai 2.27 dan materi selanjutnya dalam bahasa Inggris agar penutupan sumber dan pembangunan buku lengkap dapat direproduksi. Sufiks tersebut belum merupakan hasil terjemahan. Pekerjaan berlanjut dalam urutan sumber, dan versi berikutnya akan memakai garis keturunan konsep yang sama.

## Berkas

- `00_STATISTIKA_BERBASIS_DATA_ID_R011-B007_WORKING_READER.pdf` - salinan angkut PDF pembaca utama yang dioptimalkan secara nirhilang dari PDF yang diterima.
- `01_STATISTIKA_BERBASIS_DATA_ID_R011-B007_EDITABLE_SOURCE.zip` - penutupan sumber LaTeX dan aset yang dapat disunting untuk membangun batas R011-B007.
- `02_STATISTIKA_BERBASIS_DATA_ID_R011-B007_MODULAR_BACKEND.zip` - ekspor JSONL/CSV, skema, generator, validator, serta bukti penerimaan backend modular yang ringkas.
- `RELEASE_MANIFEST.json` dan `SHA256SUMS.txt` - inventaris ukuran dan SHA-256 seluruh muatan rilis.
- `LICENSES_AND_ATTRIBUTION.md` - atribusi, lisensi, batas merek, dan pengecualian komponen.
- `CITATION.cff` - metadata sitasi rilis.
- `ZENODO_METADATA.json` - metadata transaksi pelestarian tanpa kredensial.

## Otoritas dan identitas

Karya ini merupakan turunan Bahasa Indonesia dari *OpenIntro Statistics*, Edisi Keempat, oleh David M. Diez, Mine Çetinkaya-Rundel, dan Christopher D. Barr. Sumber dibekukan pada komit resmi `fee25091fb24e89c36296fd67c48c1fcf7a93b6e` dan pohon `d61cc601e7d97759ce805900520f784d02a0489e`.

Judul turunan ini adalah *Statistika Berbasis Data*. Karya ini bukan produk OpenIntro dan tidak berafiliasi dengan atau didukung oleh OpenIntro. Kontributor edisi Bahasa Indonesia adalah Codex, atas permintaan pengguna.

Identifikasi model produksi: **OpenAI Codex gpt-5.6-sol, Ultra**. Identifikasi ini menerangkan alat produksi edisi turunan dan tidak menggantikan atau mengurangi kredit penulis sumber maupun kontributor manusia.

## Kualitas dan keterbatasan

PDF dan backend yang diterbitkan di sini hanya akan dimasukkan setelah build berulang menghasilkan byte identik, pemeriksaan struktur dan bahasa lulus, semua halaman yang berubah beserta halaman transisinya diperiksa secara visual, dan penerimaan membaca kembali byte yang dipromosikan. Identitas akhir dicatat di `RELEASE_MANIFEST.json`.

Endpoint unggahan pelestarian menolak PDF yang diterima sebesar 22.017.185 byte dengan HTTP 413. Karena itu, berkas pembaca publik ditulis ulang secara deterministik dan nirhilang pada tingkat objek/aliran PDF menjadi 20.940.913 byte. Ke-425 halaman, metadata, bahasa dokumen, 3.406 tujuan bernama, 2.759 anotasi, teks hasil ekstraksi, dan piksel render pada seluruh 23 halaman QA tetap identik; hash PDF penerimaan dan tanda terima transformasi dicatat di `RELEASE_MANIFEST.json` dan paket backend modular.

PDF mendeklarasikan bahasa `id-ID`, tetapi belum ditandai secara struktural. Pembaca HTML yang dapat diakses tetap menjadi syarat sebelum edisi lengkap dinyatakan selesai.
