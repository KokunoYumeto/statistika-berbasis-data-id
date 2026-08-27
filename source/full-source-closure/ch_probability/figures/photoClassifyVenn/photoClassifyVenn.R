library(openintro)
data(COL)

# Proporsi tidak sepenuhnya tepat; sedikit disesuaikan demi tampilan.

pdf('photoClassifyVenn.pdf', 4.5, 2.4)
par(mar = rep(0, 4))
plot(0:1, 0:1, type = 'n', axes = FALSE)
rect(0, 0, 1, 1, lwd=2)
rect(0.10, 0.35,
     0.75, 0.58,
     border = COL[4, 2],
     col = paste0(COL[4], "25"),
     lty = 3,
     lwd = 2.512)
text(0.33, 0.28, 'ML memprediksi busana', col=COL[4,2], cex=0.85)
rect(0.18, 0.34,
     0.77, 0.69,
     border = COL[1],
     col = COL[1, 4],
     lty = 2,
     lwd = 2)
text(0.54, 0.68, 'Foto busana', col = COL[1], pos = 3)
text(0.45, 0.45, 0.11, col = COL[5])
text(0.14, 0.49, 0.01, col = COL[4], cex = 0.9)
text(0.6, 0.63, 0.06, col = COL[1])
text(0.8, 0.11, 'Bukan keduanya: 0.82', col = COL[6], cex=0.85)
dev.off()
