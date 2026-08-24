# Statistika Berbasis Data — Bahasa Indonesia

Edisi kerja Bahasa Indonesia (`id-ID`) yang diturunkan dari *OpenIntro Statistics*, Edisi Keempat. Judul turunannya sengaja berbeda; proyek ini bukan produk OpenIntro dan tidak berafiliasi dengan atau didukung oleh OpenIntro.

> **Status R011-B010: belum lengkap.** Materi pendahuluan, Bab 1–2, pembuka Bab 3, Bagian 3.1, dan Bagian 3.2 *Peluang bersyarat* telah diterjemahkan dan diterima. Materi mulai Bagian 3.3 tetap berbahasa Inggris di dalam PDF batas kerja agar build buku penuh dapat direproduksi.

## Baca dan unduh

- [PDF batas kerja R011-B010](output/pdf/statistika-berbasis-data-batas-R011-B010.pdf) — 426 halaman, 22026372 byte, SHA-256 `cfeed2f4bd124edef8ef2c6864ddf8375ee09470977492d007160f8a450a1b6b`.
- [Rilis publik terbaru yang telah diverifikasi, R011-B009](https://doi.org/10.5281/zenodo.22071153) — tetap menjadi versi publik terbaru sampai paket B010 diterbitkan dan dibaca balik.
- [Garis keturunan konsep Zenodo](https://doi.org/10.5281/zenodo.22059801) — menunjuk versi terbaru dari edisi ini.
- [Rilis GitHub publik terbaru, R011-B009](https://github.com/KokunoYumeto/statistika-berbasis-data-id/releases/tag/r011-b009-2026.08.23.1).

## Cakupan yang diterima

- pembuka Bab 3 dan Bagian 3.1 yang telah diterima pada B009;
- Bagian 3.2 lengkap, *Conditional probability* / *Peluang bersyarat*, dalam urutan sumber;
- 8 subseksi, 6 contoh bernomor, dan 15 latihan terpandu beserta jawaban publik inline;
- latihan akhir bab 13–22;
- jawaban publik 13, 15, 17, 19, dan 21;
- delapan pasangan aset diagram terlokalisasi beserta produser R yang dapat disunting;
- catatan celah `O001` untuk 14, 16, 18, 20, dan 22.

Tidak ada solusi instruktur terbatas yang diakses, direkonstruksi, atau disajikan seolah-olah berasal dari sumber. Cursor berikutnya adalah Bagian 3.3 pada label `smallPop`.

## Isi repositori

- `repo/` — penutupan sumber LaTeX dan aset tepat untuk batas R011-B010;
- `backend/exports/` dan `backend/schemas/` — rekaman modular, proyeksi, skema, dan bukti penerimaan;
- `output/pdf/` — PDF pembaca yang telah diterima;
- `qa/`, `authority/`, dan `scripts/` — bukti ringkas serta gerbang reproduksi;
- `release/` — paket, metadata, hak, checksum, dan tanda terima publikasi yang disanitasi.

## Otoritas, kredit, dan lisensi

Sumber resmi dibekukan pada repositori [`OpenIntroStat/openintro-statistics`](https://github.com/OpenIntroStat/openintro-statistics), komit `fee25091fb24e89c36296fd67c48c1fcf7a93b6e`, pohon `d61cc601e7d97759ce805900520f784d02a0489e`.

Karya sumber ditulis oleh David M. Diez, Mine Çetinkaya-Rundel, dan Christopher D. Barr. Kontributor edisi Bahasa Indonesia: Codex, atas permintaan pengguna. Identifikasi model produksi: **OpenAI Codex gpt-5.6-sol, Ultra**. Identifikasi alat ini tidak menggantikan atau mengurangi kredit penulis sumber maupun kontributor manusia.

Teks sumber dan terjemahan tersedia berdasarkan CC BY-SA 3.0, kecuali komponen yang memiliki ketentuan sendiri. Lihat [lisensi dan atribusi](LICENSE.md), `00_control/COMPONENT_RIGHTS.csv`, dan `backend/exports/core/rights.jsonl` sebelum menggunakan kembali berkas individual.
