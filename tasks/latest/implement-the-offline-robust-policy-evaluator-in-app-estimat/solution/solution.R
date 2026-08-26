args <- commandArgs(trailingOnly = TRUE)
root <- if (length(args) >= 1) args[[1]] else "/app/data"
output <- if (length(args) >= 2) args[[2]] else "/app/results.csv"

read_relation <- function(name) {
  read.csv(file.path(root, name), stringsAsFactors = FALSE, check.names = FALSE)
}

counts <- read_relation("nominal_transition_counts.csv")
policies <- read_relation("target_policies.csv")
profiles <- read_relation("ambiguity_profiles.csv")
cases <- read_relation("robust_budget_cases.csv")
cases <- cases[order(cases$case_id), , drop = FALSE]

transient <- paste0("s", 0:3)
states <- c(transient, "goal", "fail")
actions <- 0:2

is_integer_value <- function(x) {
  length(x) == 1 && is.finite(x) && x == floor(x)
}

l1_minimum <- function(probabilities, values, radius) {
  q <- probabilities
  remaining <- min(max(radius, 0), 2) / 2
  while (remaining > 1e-15) {
    sources <- which(q > 1e-15)
    sinks <- which(q < 1 - 1e-15)
    if (length(sources) == 0 || length(sinks) == 0) break
    high_value <- max(values[sources])
    low_value <- min(values[sinks])
    if (high_value <= low_value + 1e-15) break
    high <- sources[which(values[sources] == high_value)[1]]
    low <- sinks[which(values[sinks] == low_value)[1]]
    moved <- min(remaining, q[high], 1 - q[low])
    q[high] <- q[high] - moved
    q[low] <- q[low] + moved
    remaining <- remaining - moved
  }
  sum(q * values)
}

count_schema_ok <- all(
  c("state", "action", "destination", "count") %in% names(counts)
)
global_count_invalid <- !count_schema_ok
kernels <- list()
totals <- numeric(0)

for (state in transient) {
  for (action in actions) {
    key <- paste(state, action, sep = "|")
    if (count_schema_ok) {
      part <- counts[counts$state == state & counts$action == action, , drop = FALSE]
      row_values <- suppressWarnings(as.numeric(part$count))
      valid_rows <- nrow(part) > 0 &&
        all(is.finite(row_values)) &&
        all(row_values >= 0) &&
        all(part$destination %in% states)
      total <- if (nrow(part) > 0) sum(row_values) else 0
      vector <- setNames(rep(0, length(states)), states)
      if (valid_rows && total > 0) {
        for (index in seq_len(nrow(part))) {
          vector[part$destination[index]] <-
            vector[part$destination[index]] + row_values[index] / total
        }
      }
      global_count_invalid <- global_count_invalid || !valid_rows
    } else {
      total <- 0
      vector <- setNames(rep(0, length(states)), states)
    }
    totals[key] <- total
    kernels[[key]] <- vector
  }
}

rows <- vector("list", nrow(cases))

for (case_index in seq_len(nrow(cases))) {
  case <- cases[case_index, , drop = FALSE]
  minimum_count <- suppressWarnings(as.numeric(case$minimum_pair_count))
  low_count_pairs <- if (
    length(minimum_count) == 1 && is.finite(minimum_count)
  ) {
    sum(totals < minimum_count)
  } else {
    12L
  }

  horizon <- suppressWarnings(as.numeric(case$horizon))
  transport_budget <- suppressWarnings(as.numeric(case$budget_units))
  intervention_budget <- suppressWarnings(
    as.numeric(case$intervention_budget_units)
  )
  base_radius <- suppressWarnings(as.numeric(case$l1_radius_per_unit))

  invalid <- global_count_invalid ||
    any(totals <= 0) ||
    length(minimum_count) != 1 ||
    !is.finite(minimum_count) ||
    minimum_count < 0 ||
    !is_integer_value(horizon) ||
    horizon < 1 ||
    !is_integer_value(transport_budget) ||
    transport_budget < 0 ||
    !is_integer_value(intervention_budget) ||
    intervention_budget < 0 ||
    length(base_radius) != 1 ||
    !is.finite(base_radius) ||
    base_radius < 0 ||
    !(case$start_state %in% transient) ||
    low_count_pairs > 0

  policy <- list()
  for (state in transient) {
    part <- policies[
      policies$policy_id == case$policy_id & policies$state == state,
      ,
      drop = FALSE
    ]
    probabilities <- suppressWarnings(as.numeric(part$probability))
    action_values <- suppressWarnings(as.numeric(part$action))
    valid <- nrow(part) == 3 &&
      all(is.finite(probabilities)) &&
      all(probabilities > 0) &&
      setequal(action_values, actions) &&
      length(unique(action_values)) == 3 &&
      abs(sum(probabilities) - 1) <= 1e-12
    invalid <- invalid || !valid
    vector <- rep(NA_real_, 3)
    if (valid) vector[action_values + 1] <- probabilities
    policy[[state]] <- vector
  }

  profile <- list()
  for (state in transient) {
    for (action in actions) {
      part <- profiles[
        profiles$ambiguity_profile_id == case$ambiguity_profile_id &
          profiles$state == state &
          profiles$action == action,
        ,
        drop = FALSE
      ]
      cost <- suppressWarnings(as.numeric(part$budget_cost))
      multiplier <- suppressWarnings(as.numeric(part$radius_multiplier))
      cap <- suppressWarnings(as.numeric(part$max_ambiguity_units))
      valid <- nrow(part) == 1 &&
        is_integer_value(cost) &&
        cost > 0 &&
        length(multiplier) == 1 &&
        is.finite(multiplier) &&
        multiplier > 0 &&
        is_integer_value(cap) &&
        cap >= 0
      invalid <- invalid || !valid
      profile[[paste(state, action, sep = "|")]] <- c(
        cost = if (length(cost) == 1) cost else NA_real_,
        multiplier = if (length(multiplier) == 1) multiplier else NA_real_,
        cap = if (length(cap) == 1) cap else NA_real_
      )
    }
  }

  unsupported <- invalid
  if (!unsupported) {
    H <- as.integer(horizon)
    B <- as.integer(transport_budget)
    C <- as.integer(intervention_budget)
    V <- array(
      0,
      dim = c(H + 1, length(states), B + 1, C + 1),
      dimnames = list(NULL, states, NULL, NULL)
    )
    V[, "goal", , ] <- 1
    nominal <- matrix(
      0,
      nrow = H + 1,
      ncol = length(states),
      dimnames = list(NULL, states)
    )
    nominal[, "goal"] <- 1
    transport_residual <- 0
    intervention_residual <- 0

    enumerate_plans <- function(state, budget, interventions) {
      parameters <- lapply(actions, function(action) {
        profile[[paste(state, action, sep = "|")]]
      })
      maxima <- vapply(parameters, function(item) {
        as.integer(min(as.integer(item["cap"]), floor(budget / item["cost"])))
      }, integer(1))
      grid <- expand.grid(lapply(maxima, function(maximum) 0:maximum))
      names(grid) <- paste0("u", actions)
      grid <- grid[do.call(order, grid[paste0("u", actions)]), , drop = FALSE]
      costs <- vapply(seq_len(nrow(grid)), function(index) {
        sum(vapply(actions, function(action) {
          grid[index, action + 1] * parameters[[action + 1]]["cost"]
        }, numeric(1)))
      }, numeric(1))
      active <- rowSums(grid > 0)
      keep <- costs <= budget & active <= interventions
      list(
        units = grid[keep, , drop = FALSE],
        costs = costs[keep],
        active = active[keep],
        parameters = parameters
      )
    }

    evaluate_plan <- function(state, h_index, budget, interventions, plan, total_cost, active) {
      child <- V[h_index, , budget - total_cost + 1, interventions - active + 1]
      sum(vapply(actions, function(action) {
        key <- paste(state, action, sep = "|")
        parameters <- profile[[key]]
        policy[[state]][action + 1] * l1_minimum(
          kernels[[key]],
          child,
          plan[action + 1] * base_radius * parameters["multiplier"]
        )
      }, numeric(1)))
    }

    for (h in seq_len(H)) {
      for (state in transient) {
        nominal[h + 1, state] <- sum(vapply(
          actions,
          function(action) {
            key <- paste(state, action, sep = "|")
            policy[[state]][action + 1] *
              sum(kernels[[key]] * nominal[h, ])
          },
          numeric(1)
        ))

        for (b in 0:B) {
          for (c_budget in 0:C) {
            plans <- enumerate_plans(state, b, c_budget)
            candidate_values <- vapply(seq_len(nrow(plans$units)), function(index) {
              evaluate_plan(
                state,
                h,
                b,
                c_budget,
                as.numeric(plans$units[index, ]),
                plans$costs[index],
                plans$active[index]
              )
            }, numeric(1))
            best <- min(candidate_values)
            chosen <- which(candidate_values <= best + 1e-12)[1]
            V[h + 1, state, b + 1, c_budget + 1] <- candidate_values[chosen]
          }
        }

        if (B > 0) {
          transport_residual <- max(
            transport_residual,
            V[h + 1, state, 2:(B + 1), , drop = FALSE] -
              V[h + 1, state, 1:B, , drop = FALSE],
            0
          )
        }
        if (C > 0) {
          intervention_residual <- max(
            intervention_residual,
            V[h + 1, state, , 2:(C + 1), drop = FALSE] -
              V[h + 1, state, , 1:C, drop = FALSE],
            0
          )
        }
      }
    }

    start <- case$start_state
    robust <- V[H + 1, start, B + 1, C + 1]
    nominal_value <- nominal[H + 1, start]
    initial_plans <- enumerate_plans(start, B, C)
    initial_values <- vapply(seq_len(nrow(initial_plans$units)), function(index) {
      evaluate_plan(
        start,
        H,
        B,
        C,
        as.numeric(initial_plans$units[index, ]),
        initial_plans$costs[index],
        initial_plans$active[index]
      )
    }, numeric(1))
    initial_best <- min(initial_values)
    initial_index <- which(initial_values <= initial_best + 1e-12)[1]
    initial_units <- as.numeric(initial_plans$units[initial_index, ])
    expected_units <- sum(policy[[start]] * initial_units)
    expected_cost <- initial_plans$costs[initial_index]
    expected_active <- initial_plans$active[initial_index]
    gap <- nominal_value - robust
    diagnostics <- c(
      robust,
      nominal_value,
      gap,
      expected_units,
      expected_cost,
      expected_active,
      transport_residual,
      intervention_residual
    )
    unsupported <- any(!is.finite(diagnostics))
  }

  if (unsupported) {
    rows[[case_index]] <- data.frame(
      case_id = case$case_id,
      unsupported = 1L,
      low_count_pairs = as.integer(low_count_pairs),
      robust_reachability = NA_real_,
      nominal_reachability = NA_real_,
      robust_gap = NA_real_,
      initial_expected_ambiguity_units = NA_real_,
      initial_expected_budget_cost = NA_real_,
      initial_expected_intervention = NA_real_,
      transport_monotonicity_residual = NA_real_,
      intervention_monotonicity_residual = NA_real_
    )
  } else {
    rows[[case_index]] <- data.frame(
      case_id = case$case_id,
      unsupported = 0L,
      low_count_pairs = 0L,
      robust_reachability = robust,
      nominal_reachability = nominal_value,
      robust_gap = gap,
      initial_expected_ambiguity_units = expected_units,
      initial_expected_budget_cost = expected_cost,
      initial_expected_intervention = expected_active,
      transport_monotonicity_residual = transport_residual,
      intervention_monotonicity_residual = intervention_residual
    )
  }
}

write.csv(
  do.call(rbind, rows),
  output,
  row.names = FALSE,
  quote = FALSE,
  na = ""
)
