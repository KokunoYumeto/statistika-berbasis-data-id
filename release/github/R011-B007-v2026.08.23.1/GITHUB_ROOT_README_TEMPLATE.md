# Statistika Berbasis Data — Bahasa Indonesia

Edisi kerja Bahasa Indonesia (`id-ID`) yang diturunkan dari *OpenIntro Statistics*, Edisi Keempat. Judul turunannya sengaja berbeda; proyek ini bukan produk OpenIntro dan tidak berafiliasi dengan atau didukung oleh OpenIntro.

> **Status R011-B007: belum lengkap.** Materi pendahuluan, Bab 1 lengkap, pembuka Bab 2, serta Bagian 2.1–2.3 telah diterjemahkan dan diterima. Latihan tinjauan Bab 2 mulai 2.27 dan materi selanjutnya masih berbahasa Inggris di dalam PDF batas kerja agar build buku penuh tetap dapat direproduksi.

## Baca dan unduh

- [PDF batas kerja R011-B007](output/pdf/statistika-berbasis-data-batas-R011-B007.pdf) — @@PDF_PAGES@@ halaman, @@CANONICAL_PDF_BYTES@@ byte, SHA-256 `@@CANONICAL_PDF_SHA256@@`.
- [Rilis pelestarian tetap di Zenodo](https://doi.org/@@ZENODO_DOI@@) — PDF, sumber editable, backend modular, manifes, dan checksum.
- [Cermin publik di Figshare](@@FIGSHARE_URL@@) — DOI `@@FIGSHARE_DOI@@`.
- [Garis keturunan konsep Zenodo](https://doi.org/10.5281/zenodo.22059801) — selalu menunjuk versi terbaru dari edisi ini.

PDF pelestarian memakai penulisan ulang transport lossless yang deterministik: @@READER_PDF_BYTES@@ byte, SHA-256 `@@READER_PDF_SHA256@@`. Isi teks, tujuan bernama, anotasi, metadata, jumlah halaman, dan piksel halaman audit identik dengan PDF batas yang diterima.

## Cakupan yang diterima

- halaman judul, atribusi, dan materi pendahuluan turunan;
- Bab 1, Bagian 1.1–1.4, latihan 1.35–1.44, dan jawaban publik yang tersedia;
- pembuka Bab 2 dan Bagian 2.1, *Menelaah data numerik*;
- Bagian 2.2, *Menelaah data kategoris*;
- Bagian 2.3, *Studi kasus: vaksin malaria*, termasuk latihan 2.25–2.26;
- semua jawaban publik yang tersedia sampai latihan 2.25.

Latihan tanpa jawaban publik dicatat sebagai celah pendamping `O001`. Tidak ada solusi instruktur terbatas yang diakses, direkonstruksi, atau disajikan seolah-olah berasal dari sumber. Cursor berikutnya adalah latihan tinjauan Bab 2 mulai 2.27.

## Isi repositori

- `repo/` — penutupan sumber LaTeX dan aset tepat untuk batas R011-B007;
- `backend/exports/` dan `backend/schemas/` — @@BACKEND_RECORDS@@ rekaman bertipe, proyeksi CSV, pelokalan `id-ID`, skema, serta bukti penerimaan;
- `output/pdf/` — PDF pembaca yang telah diterima;
- `qa/`, `authority/`, dan `scripts/` — bukti ringkas serta gerbang reproduksi yang mengikat batas R011-B007;
- `release/` — metadata dan tanda terima publikasi yang telah disanitasi.

## Otoritas dan reproduksi

Sumber resmi dibekukan pada repositori [`OpenIntroStat/openintro-statistics`](https://github.com/OpenIntroStat/openintro-statistics), komit `fee25091fb24e89c36296fd67c48c1fcf7a93b6e`, pohon `d61cc601e7d97759ce805900520f784d02a0489e`.

Build statis memakai gambar yang sudah dikomit dan urutan berikut dari dalam `repo/`:

```text
pdflatex main.tex
bibtex main
makeindex main.idx
pdflatex main.tex
makeindex main.idx
pdflatex main.tex
makeindex main.idx
pdflatex main.tex
```

## Lisensi, atribusi, dan merek

Teks sumber dan terjemahan tersedia berdasarkan CC BY-SA 3.0, kecuali komponen yang memiliki ketentuan sendiri. Lihat [lisensi dan atribusi](LICENSE.md), `00_control/COMPONENT_RIGHTS.csv`, dan `backend/exports/core/rights.jsonl` sebelum menggunakan kembali berkas individual.

Karya sumber ditulis oleh David M. Diez, Mine Çetinkaya-Rundel, dan Christopher D. Barr. Kontributor edisi Bahasa Indonesia: Codex, atas permintaan pengguna. Merek dagang, logo, sampul, dan identitas visual OpenIntro tidak digunakan sebagai identitas karya turunan ini.

Identifikasi model produksi: **OpenAI Codex gpt-5.6-sol, Ultra**. Identifikasi ini menerangkan alat produksi edisi turunan dan tidak menggantikan atau mengurangi kredit penulis sumber maupun kontributor manusia.
