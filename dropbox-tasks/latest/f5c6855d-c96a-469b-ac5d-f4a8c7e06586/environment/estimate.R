args <- commandArgs(trailingOnly = TRUE)
data_dir <- if (length(args) >= 1) args[[1]] else "/app/data"
output_path <- if (length(args) >= 2) args[[2]] else "/app/results.csv"
write.csv(data.frame(), output_path, row.names = FALSE, quote = FALSE)
