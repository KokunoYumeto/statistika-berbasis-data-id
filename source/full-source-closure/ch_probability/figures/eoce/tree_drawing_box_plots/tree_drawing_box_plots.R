# Muat openintro untuk fungsi treeDiag.
library(openintro)

pdf('tree_drawing_box_plots.pdf', width = 6, height = 2.5)
treeDiag(c('\nDapat membuat\ndiagram kotak?', 'Lulus?'),
         c(0.80, 0.20), list(c(0.86, 0.14), c(0.65, 0.35)),
         c('ya', 'tidak'), textwd = 0.19, solwd = 0.25, showWork = TRUE,
         col.main = COL[1])
dev.off()
