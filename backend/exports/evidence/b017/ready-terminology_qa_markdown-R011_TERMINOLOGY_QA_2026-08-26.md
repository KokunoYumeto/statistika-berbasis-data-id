# QA istilah bidang R011 pada batas B017

Status: **lulus; tidak ada perubahan istilah atau propagasi yang dibenarkan**.

Pencarian terbatas melalui API resmi arXiv tidak menemukan naskah TeX berbahasa Indonesia yang sesuai dengan bidang statistika/probabilitas. Pencarian mencakup frasa istilah inti, kategori `stat.*` dan `math.PR`, serta 17 hasil untuk frasa “Bahasa Indonesia”; seluruh judul hasil terakhir diperiksa dan bukan sumber inti statistika/probabilitas. Kesimpulan ini hanya berlaku untuk pencarian terbatas tersebut.

Saksi pengganti utama ialah artikel Maria Selviana, Astri Atti, Jusrry Rosalina Pahnael, dan Robertus Dole Guntur, “Model Regresi Poisson untuk Menganalisis Faktor-Faktor yang Berpengaruh terhadap Jumlah Pengangguran di Nusa Tenggara Timur,” *MATHunesa: Jurnal Ilmiah Matematika* 13(3) (2025), DOI `10.26740/mathunesa.v13n3.p156-164`. Akhiran DOI menyebut halaman 156-164, sedangkan PDF 8 halaman yang diunduh tampak bernomor cetak 156-163; catatan ini mempertahankan kedua bukti tanpa menebak. PDF diekstrak dengan `pdftotext -layout`, dan halaman fisik 1-3 diperiksa secara visual. Halaman fisik 3/halaman cetak 158 secara langsung memakai `Distribusi Binomial Negatif`, `jumlah percobaan`, `probabilitas sukses`, `nilai harapan`, serta bentuk `kegagalan` dan `keberhasilan`.

PDF: 487.630 byte; SHA-256 `e8fe006aa7fe17256b05d5cdf464450cc87ef01af686d797bbac0128f1f271a6`. Ekstraksi teks: 49.037 byte; SHA-256 `1d517c74f1b2248da286d144494094ddc25f552900957b9e6fdfd6c1a2e53a49`. Laman artikel menyatakan CC BY-NC 4.0; berkas saksi ini hanya untuk QA internal dan tidak boleh dimasukkan ke paket edisi.

Modul resmi Universitas Jember karya I Made Tirta, *Modul Distribusi Diskrit* (September 2022), dipakai sebagai saksi tambahan untuk istilah yang tidak muncul dalam artikel: `Distribusi Geometrik`, `percobaan saling bebas`, `sukses`, `gagal`, dan `kombinasi`. Server asal mengembalikan HTTP 502 ketika pengunduhan langsung dicoba, sehingga tidak ada hash lokal yang diklaim untuk modul web tersebut.

Keputusan istilah:

- `negative binomial distribution` → `distribusi binomial negatif`: pertahankan.
- `geometric distribution` → `distribusi geometrik`: pertahankan; `distribusi geometri` sudah tercatat sebagai varian.
- `trial` → `percobaan`: pertahankan; `ulangan` teramati, tetapi kurang tepat sebagai label utama yang seragam.
- `independent` → `saling independen`: pertahankan; `saling bebas` sudah tercatat sebagai sinonim.
- `success`/`failure` → `sukses`/`gagal`: pertahankan; bentuk nominal `keberhasilan`/`kegagalan` sudah tertangani.
- `probability` → `peluang`: pertahankan untuk nilai peristiwa; `probabilitas` tetap sebagai bentuk bertata lingkup.
- `factorial` → `faktorial`: pertahankan; tidak ada bentuk saingan dalam saksi baru.
- `combination` → `kombinasi`, dengan `n pilih k` dalam rumus: pertahankan.
- `expected value` → `nilai harapan`: pertahankan; dibuktikan langsung oleh artikel.
- `standard deviation` → `simpangan baku`: pertahankan; tidak ada bukti baru yang berlawanan.

Catatan model yang diwajibkan sudah ada pada `README.md` baris 37 dengan identifikasi persis **OpenAI Codex gpt-5.6-sol, Ultra**, tanpa mengurangi kredit penulis sumber atau kontributor manusia. Tidak ada berkas kanonis, backend, atau publikasi yang diubah dalam QA ini.
