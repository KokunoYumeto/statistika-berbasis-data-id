library(openintro)

myPDF('treeDiagramAndPass.pdf', 6, 2.7)
treeDiag(c('\nMampu membuat\ndiagram pohon', 'Lulus mata kuliah'),
         c(0.78, 0.22),
         list(c(0.97, 0.03),
              c(0.57, 0.43)),
         textwd = 0.2,
         solwd = 0.35,
         cex.main = 1.1,
         c('ya', 'tidak'),
         c('lulus', 'gagal'),
         digits = 5,
         col.main = COL[1],
         showWork = TRUE)
dev.off()
