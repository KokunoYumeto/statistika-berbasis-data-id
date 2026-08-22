# Statistika Berbasis Data — Bahasa Indonesia

Edisi kerja Bahasa Indonesia (`id-ID`) yang diturunkan dari *OpenIntro Statistics*, Edisi Keempat. Judul turunannya sengaja berbeda; proyek ini bukan produk OpenIntro dan tidak berafiliasi dengan atau didukung oleh OpenIntro.

> **Status R011-B006: belum lengkap.** Materi pendahuluan, Bab 1 lengkap, pembuka Bab 2, serta Bagian 2.1–2.2 telah diterjemahkan dan diterima. Bagian 2.3 dan seterusnya masih berbahasa Inggris di dalam PDF batas kerja agar build buku penuh tetap dapat direproduksi.

## Baca dan unduh

- [PDF batas kerja R011-B006](output/pdf/statistika-berbasis-data-batas-R011-B006.pdf) — 424 halaman, 21.975.722 byte, SHA-256 `d9a3df7d44a62babde04c355cb8dbb9edc74de947cc8162a3d30d872bea372b2`.
- [Rilis pelestarian tetap di Zenodo](https://doi.org/10.5281/zenodo.22061163) — PDF, sumber editable, backend modular, bukti QA, manifes, dan checksum.
- [Garis keturunan konsep Zenodo](https://doi.org/10.5281/zenodo.22059801) — selalu menunjuk versi terbaru dari edisi ini.

## Cakupan yang diterima

- halaman judul, atribusi, dan materi pendahuluan turunan;
- Bab 1, Bagian 1.1–1.4;
- latihan akhir Bab 1 nomor 1.35–1.44 dan semua jawaban publik yang tersedia;
- pembuka Bab 2 dan Bagian 2.1, *Menelaah data numerik*;
- Bagian 2.2, *Menelaah data kategoris*;
- latihan 2.1–2.24 dan semua jawaban publik bernomor ganjil yang tersedia sampai batas ini.

Latihan tanpa jawaban publik dicatat sebagai celah pendamping `O001`. Tidak ada solusi instruktur terbatas yang diakses, direkonstruksi, atau disajikan seolah-olah berasal dari sumber. Cursor berikutnya adalah Bagian 2.3, *Studi kasus: vaksin malaria*.

## Isi repositori

- `repo/` — sumber LaTeX dan aset tepat untuk membangun batas R011-B006;
- `backend/exports/` dan `backend/schemas/` — 1.969 rekaman bertipe, 8.647 referensi terselesaikan, tampilan CSV, pelokalan `id-ID`, skema, dan bukti;
- `output/pdf/` — PDF pembaca yang telah diterima;
- `qa/`, `authority/`, dan `scripts/` — bukti ringkas serta gerbang reproduksi yang secara khusus mengikat batas R011-B006;
- `release/zenodo/R011-B006-v2026.08.22.2/` — metadata, manifes, checksum, dan tanda terima publikasi yang telah disanitasi.

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

Build yang diterima memakai MiKTeX 26.5; dua lintasan PDF terakhir identik byte demi byte. Generator gambar R disertakan jika tersedia, tetapi tidak diperlukan untuk build statis. Build gambar global belum hermetik karena upstream tidak menyediakan driver global maupun lockfile dependensi.

## Lisensi, atribusi, dan merek

Teks sumber dan terjemahan tersedia berdasarkan CC BY-SA 3.0, kecuali komponen yang memiliki ketentuan sendiri. Lihat [lisensi dan atribusi](LICENSE.md) serta `00_control/COMPONENT_RIGHTS.csv` dan `backend/exports/core/rights.jsonl` sebelum menggunakan kembali berkas individual.

Karya sumber ditulis oleh David M. Diez, Mine Çetinkaya-Rundel, dan Christopher D. Barr. Kontributor edisi Bahasa Indonesia: Codex, atas permintaan Floris. Merek dagang, logo, sampul, dan identitas visual OpenIntro tidak digunakan sebagai identitas karya turunan ini.

