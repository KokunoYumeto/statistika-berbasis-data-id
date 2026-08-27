# muat palet dan perangkat PDF yang dibekukan -----------------------
source("../../b003_replay_helpers.R")

# muat data ---------------------------------------------------------
load("factbook.rda")
# Kumpulan data ini juga tersedia dengan nama yang sama dalam paket
# cia_factbook.

# hitung persentase pengguna internet -------------------------------
cia_factbook$internet_perc = cia_factbook$internet_users / cia_factbook$population * 100

# hitung negara dengan data internet dan harapan hidup --------------
n_complete <- sum(complete.cases(
  cia_factbook$internet_perc,
  cia_factbook$life_exp_at_birth
))
stopifnot(nrow(cia_factbook) == 259, n_complete == 208)

# diagram pencar harapan hidup terhadap pengguna internet -----------
pdf("internet_life_expectancy.pdf", 6, 4.3)
par(mar = c(4, 4.1, 1, 1), las = 1, mgp = c(2.9, 0.7, 0), 
    cex.axis = 1.5, cex.lab = 1.5)
plot(cia_factbook$life_exp_at_birth ~ cia_factbook$internet_perc, 
     xlab = "Persentase Pengguna Internet",
     ylab = "Harapan Hidup Saat Lahir", 
     pch = 20, col = COL[1,2], cex.lab = 1.5, cex.axis = 1.5,
     xlim = c(0,100),
     axes = FALSE)
AxisInPercent(1, at = seq(0, 100, 20))
axis(2)
box()
dev.off()
