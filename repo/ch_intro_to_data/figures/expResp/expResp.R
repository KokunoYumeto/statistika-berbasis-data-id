
pdf("expResp.pdf", 3.82, 0.44)
par(mar = rep(0, 4))
plot(0:1, 0:1, type = 'n', axes = FALSE)
arrows(0.3, 0.4, 0.7, 0.4, length = 0.1)
text(0.5, 0.3, 'mungkin memengaruhi', pos = 3, cex = 0.7)
text(0.15, 0.5, 'variabel\npenjelas')
text(0.85, 0.5, 'variabel\nrespons')
dev.off()
