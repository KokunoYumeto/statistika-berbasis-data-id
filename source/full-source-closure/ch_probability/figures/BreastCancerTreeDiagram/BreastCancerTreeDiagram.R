library(openintro)

myPDF('BreastCancerTreeDiagram.pdf', 7.5, 2.5)
treeDiag(c('Kondisi', 'Mamogram'),
         c(0.0035, 0.9965),
         list(c(0.89, 0.11),
              c(0.07, 0.93)),
         textwd = 0.2,
         solwd = 0.35,
         cex.main = 1.4,
         c('kanker', 'tanpa kanker'),
         c('positif', 'negatif'),
         digits = 5,
         col.main = COL[1],
         showWork = TRUE)
dev.off()
