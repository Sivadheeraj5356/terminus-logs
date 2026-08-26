#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
input_dir <- if (length(args) >= 1) args[[1]] else "/app/data"
output_path <- if (length(args) >= 2) args[[2]] else "/app/design_output.csv"

read_required <- function(name) {
  path <- file.path(input_dir, name)
  if (!file.exists(path)) {
    stop(paste("missing input file", path))
  }
  read.csv(path, stringsAsFactors = FALSE, check.names = FALSE)
}

measured <- read_required("measured_runs.csv")
candidates <- read_required("candidate_runs.csv")
costs <- read_required("candidate_costs.csv")
limits <- read_required("design_limits.csv")
quota_rules <- read_required("quota_rules.csv")
pair_rules <- read_required("pair_rules.csv")
stress_scenarios <- read_required("stress_scenarios.csv")
precision_rules <- read_required("precision_rules.csv")
dropout_rules <- read_required("dropout_rules.csv")
scaling <- read_required("scaling.csv")
model_terms <- read_required("model_terms.csv")
target_contrasts <- read_required("target_contrasts.csv")
target_weights <- read_required("target_weights.csv")

cost_index <- match(candidates$candidate_id, costs$candidate_id)
if (any(is.na(cost_index))) {
  stop("every candidate needs a cost")
}
candidates$cost <- as.numeric(costs$cost[cost_index])

get_limit <- function(column) {
  if (!(column %in% names(limits))) {
    stop(paste("missing limit", column))
  }
  limits[[column]][[1]]
}

required_new_runs <- as.integer(get_limit("required_new_runs"))
budget <- as.numeric(get_limit("budget"))
max_per_case <- as.integer(get_limit("max_per_case"))
max_per_condition_family <- as.integer(get_limit("max_per_condition_family"))
min_materials <- as.integer(get_limit("min_materials"))
min_depth_levels <- as.integer(get_limit("min_depth_levels"))
min_feed_levels <- as.integer(get_limit("min_feed_levels"))
rank_tolerance <- as.numeric(get_limit("rank_tolerance"))
tie_abs_tolerance <- as.numeric(get_limit("tie_abs_tolerance"))
tie_rel_tolerance <- as.numeric(get_limit("tie_rel_tolerance"))

scale_column <- function(values, variable) {
  row <- scaling[scaling$variable == variable, , drop = FALSE]
  if (nrow(row) != 1) {
    stop(paste("scaling row missing for", variable))
  }
  (as.numeric(values) - as.numeric(row$center[[1]])) / as.numeric(row$scale[[1]])
}

model_matrix <- function(runs) {
  values <- data.frame(
    intercept = rep(1.0, nrow(runs)),
    elapsed = scale_column(runs$elapsed_min, "elapsed"),
    depth = scale_column(runs$depth_mm, "depth"),
    feed = scale_column(runs$feed_mm_rev, "feed"),
    steel = ifelse(as.integer(runs$material_code) == 2L, 1.0, 0.0),
    current_dc = scale_column(runs$current_dc_mean, "current_dc"),
    vibration_table = scale_column(runs$vibration_table_rms, "vibration_table"),
    acoustic_spindle = scale_column(runs$acoustic_spindle_rms, "acoustic_spindle"),
    wear_stage = scale_column(runs$run_in_case, "wear_stage"),
    stringsAsFactors = FALSE,
    check.names = FALSE
  )
  values$depth_feed <- values$depth * values$feed
  values$elapsed_wear <- values$elapsed * values$wear_stage
  values$steel_depth <- values$steel * values$depth
  missing_terms <- setdiff(model_terms$term, names(values))
  if (length(missing_terms) > 0) {
    stop(paste("unsupported model terms", paste(missing_terms, collapse = ",")))
  }
  as.matrix(values[, model_terms$term, drop = FALSE])
}

contrast_vectors <- function() {
  ids <- unique(target_weights$target_id)
  vectors <- list()
  for (target_id in ids) {
    weight_row <- target_weights[target_weights$target_id == target_id, , drop = FALSE]
    contrast_rows <- target_contrasts[target_contrasts$target_id == target_id, , drop = FALSE]
    coefficients <- setNames(rep(0.0, nrow(model_terms)), model_terms$term)
    for (i in seq_len(nrow(contrast_rows))) {
      term <- contrast_rows$term[[i]]
      if (!(term %in% names(coefficients))) {
        stop(paste("unknown contrast term", term))
      }
      coefficients[[term]] <- as.numeric(contrast_rows$coefficient[[i]])
    }
    vectors[[length(vectors) + 1]] <- list(
      weight = as.numeric(weight_row$target_weight[[1]]),
      vector = as.numeric(coefficients[model_terms$term])
    )
  }
  vectors
}

count_distinct <- function(values) {
  length(unique(as.character(values)))
}

limit_repeated <- function(values, maximum) {
  counts <- table(as.character(values))
  length(counts) == 0 || max(counts) <= maximum
}

blank_value <- function(value) {
  is.na(value) || trimws(as.character(value)) == ""
}

feasible_subset <- function(subset) {
  if (sum(as.numeric(subset$cost)) > budget + 1e-9) {
    return(FALSE)
  }
  if (!limit_repeated(subset$case_id, max_per_case)) {
    return(FALSE)
  }
  if (!limit_repeated(subset$condition_family, max_per_condition_family)) {
    return(FALSE)
  }
  if (count_distinct(subset$material_label) < min_materials) {
    return(FALSE)
  }
  if (count_distinct(subset$depth_level) < min_depth_levels) {
    return(FALSE)
  }
  if (count_distinct(subset$feed_level) < min_feed_levels) {
    return(FALSE)
  }
  for (i in seq_len(nrow(quota_rules))) {
    column <- quota_rules$column[[i]]
    if (!(column %in% names(subset))) {
      stop(paste("unknown quota column", column))
    }
    count <- sum(as.character(subset[[column]]) == as.character(quota_rules$value[[i]]))
    if (!blank_value(quota_rules$min_selected[[i]]) &&
        count < as.integer(quota_rules$min_selected[[i]])) {
      return(FALSE)
    }
    if (!blank_value(quota_rules$max_selected[[i]]) &&
        count > as.integer(quota_rules$max_selected[[i]])) {
      return(FALSE)
    }
  }
  selected_ids <- as.character(subset$candidate_id)
  for (i in seq_len(nrow(pair_rules))) {
    left <- as.character(pair_rules$left_candidate_id[[i]])
    right <- as.character(pair_rules$right_candidate_id[[i]])
    rule_type <- as.character(pair_rules$rule_type[[i]])
    if (rule_type == "mutex") {
      if (left %in% selected_ids && right %in% selected_ids) {
        return(FALSE)
      }
    } else if (rule_type == "requires") {
      if (left %in% selected_ids && !(right %in% selected_ids)) {
        return(FALSE)
      }
    } else {
      stop(paste("unknown pair rule", rule_type))
    }
  }
  TRUE
}

write_result <- function(status, selected_ids, objective_value, rank_value, total_cost,
                         target_count, scenario_count, worst_scenario_id) {
  result <- data.frame(
    status = status,
    selected_ids = selected_ids,
    objective_value = objective_value,
    rank = rank_value,
    total_cost = total_cost,
    target_count = target_count,
    scenario_count = scenario_count,
    worst_scenario_id = worst_scenario_id,
    stringsAsFactors = FALSE
  )
  write.csv(result, output_path, row.names = FALSE, na = "NA")
}

scenario_survivors <- function(subset, scenario_id) {
  rules <- dropout_rules[dropout_rules$scenario_id == scenario_id, , drop = FALSE]
  if (nrow(rules) == 0) {
    return(subset)
  }
  subset[!(as.character(subset$candidate_id) %in% as.character(rules$candidate_id)), , drop = FALSE]
}

scenario_precision <- function(runs, scenario_id) {
  weights <- as.numeric(runs$precision_weight)
  rules <- precision_rules[precision_rules$scenario_id == scenario_id, , drop = FALSE]
  for (i in seq_len(nrow(rules))) {
    column <- as.character(rules$column[[i]])
    if (!(column %in% names(runs))) {
      stop(paste("unknown precision-rule column", column))
    }
    matches <- as.character(runs[[column]]) == as.character(rules$value[[i]])
    weights[matches] <- weights[matches] * as.numeric(rules$multiplier[[i]])
  }
  weights
}

objective_tolerance <- function(left, right) {
  tie_abs_tolerance + tie_rel_tolerance * max(1.0, abs(left), abs(right))
}

n <- nrow(candidates)
p <- nrow(model_terms)
targets <- contrast_vectors()
target_count <- length(targets)
scenario_ids <- as.character(stress_scenarios$scenario_id)
scenario_count <- length(scenario_ids)
if (scenario_count == 0 || anyDuplicated(scenario_ids)) {
  stop("stress_scenarios.csv needs unique scenario IDs")
}
scenario_regret_weights <- setNames(
  as.numeric(stress_scenarios$regret_weight), scenario_ids
)
if (required_new_runs < 0 || required_new_runs > n) {
  write_result(
    "infeasible", "", NA_real_, 0L, NA_real_, target_count, scenario_count, ""
  )
  quit(status = 0)
}

measured_x <- model_matrix(measured)
best_rank <- 0L
baselines <- setNames(rep(Inf, scenario_count), scenario_ids)
records <- list()

evaluate_scenario <- function(subset, scenario_id) {
  survivors <- scenario_survivors(subset, scenario_id)
  combined_x <- rbind(measured_x, model_matrix(survivors))
  combined_weights <- c(
    scenario_precision(measured, scenario_id),
    scenario_precision(survivors, scenario_id)
  )
  weighted_x <- sweep(combined_x, 1, sqrt(combined_weights), `*`)
  singular_values <- svd(weighted_x, nu = 0, nv = 0)$d
  rank_value <- sum(singular_values > rank_tolerance)
  if (rank_value < p) {
    return(list(value = NA_real_, rank = rank_value))
  }
  information <- crossprod(combined_x, combined_weights * combined_x)
  objective <- 0.0
  for (target in targets) {
    component <- tryCatch(solve(information, target$vector), error = function(e) NULL)
    if (is.null(component)) {
      return(list(value = NA_real_, rank = rank_value))
    }
    objective <- objective + target$weight * as.numeric(crossprod(target$vector, component))
  }
  list(value = objective, rank = rank_value)
}

if (required_new_runs == 0) {
  combinations <- matrix(integer(0), nrow = 0, ncol = 1)
} else {
  combinations <- combn(seq_len(n), required_new_runs)
}

for (col_index in seq_len(ncol(combinations))) {
  idx <- combinations[, col_index]
  subset <- candidates[idx, , drop = FALSE]
  if (!feasible_subset(subset)) {
    next
  }
  scenario_values <- setNames(rep(NA_real_, scenario_count), scenario_ids)
  scenario_ranks <- setNames(rep(0L, scenario_count), scenario_ids)
  for (scenario_id in scenario_ids) {
    evaluated <- evaluate_scenario(subset, scenario_id)
    scenario_values[[scenario_id]] <- evaluated$value
    scenario_ranks[[scenario_id]] <- evaluated$rank
    if (!is.na(evaluated$value)) {
      baselines[[scenario_id]] <- min(baselines[[scenario_id]], evaluated$value)
    }
  }
  ids <- sort(as.character(subset$candidate_id))
  joined <- paste(ids, collapse = ";")
  robust_rank <- min(scenario_ranks)
  best_rank <- max(best_rank, robust_rank)
  records[[length(records) + 1]] <- list(
    selected_ids = joined,
    total_cost = sum(as.numeric(subset$cost)),
    rank = robust_rank,
    values = scenario_values
  )
}

scored <- list()
if (length(records) > 0 && all(is.finite(baselines))) {
  for (record in records) {
    if (any(is.na(record$values))) {
      next
    }
    scenario_scores <- scenario_regret_weights * (record$values / baselines - 1.0)
    robust_value <- max(scenario_scores)
    worst_ids <- names(scenario_scores)[vapply(
      scenario_scores,
      function(score) abs(score - robust_value) <= objective_tolerance(score, robust_value),
      logical(1)
    )]
    record$objective_value <- robust_value
    record$worst_scenario_id <- sort(worst_ids)[[1]]
    scored[[length(scored) + 1]] <- record
  }
}

if (length(scored) == 0) {
  write_result(
    "infeasible", "", NA_real_, best_rank, NA_real_, target_count, scenario_count, ""
  )
  quit(status = 0)
}

minimum <- min(vapply(scored, function(record) record$objective_value, numeric(1)))
tied <- Filter(
  function(record) {
    abs(record$objective_value - minimum) <=
      objective_tolerance(record$objective_value, minimum)
  },
  scored
)
best <- tied[[order(vapply(tied, function(record) record$selected_ids, character(1)))[[1]]]]
write_result(
  "optimal",
  best$selected_ids,
  best$objective_value,
  best$rank,
  best$total_cost,
  target_count,
  scenario_count,
  best$worst_scenario_id
)
