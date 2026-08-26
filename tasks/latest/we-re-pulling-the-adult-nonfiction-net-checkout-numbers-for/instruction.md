We're pulling the adult-nonfiction net-checkout numbers for the fiscal-year-2024
board report and need them broken down by branch. The consortium's operational
data lake is at /app/data: the per-event circulation log, the item catalog,
branches, patrons, holds, fines, and a lot of other operational exports. Some of
these describe circulation in more than one way or are summaries, so part of the
work is figuring out which exports actually answer the question and reconciling
them into one consistent figure. /app/docs/codebook.md is the data dictionary and
/app/docs/question.md lists the exact output fields.

Fiscal year 2024 runs 2024-07-01 through 2025-06-30 on the consortium's local
America/Chicago calendar. A net checkout is a genuine checkout, not a renewal, a
return, or a filled hold. The adult-nonfiction collection is the set of items
whose item type maps to ADULT_NONFICTION.

Write your analysis as an R script at /app/analysis.R, replacing the placeholder
that is already there. It must read the lake from the directory named by the
DATALAKE_DIR environment variable, falling back to /app/data when that variable
is unset, and write the result to /app/answer.json. Input helpers are available
at /app/R/io_helpers.R if you want them. Use absolute paths.
