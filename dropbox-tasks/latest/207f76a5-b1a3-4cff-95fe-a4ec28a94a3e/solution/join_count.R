#!/usr/bin/env Rscript

# Exact spatial-autocorrelation report for a binary label and a numeric attribute
# on an areal map. Three diagnostics share one weight geometry: join counts of the
# label under free and nonfree nulls, and Moran's I / Geary's C of the numeric
# attribute under the randomization null, each on the first-order contiguity W1 and
# the derived second-order (lag-2) contiguity W2, plus Moran's I on the
# row-standardized W1. All arithmetic is exact rational (gmp bigq/bigz).

suppressWarnings(suppressMessages(library(gmp)))

fail <- function() {
  cat("ERROR\n")
  quit(save = "no", status = 0)
}

read_lines_strict <- function(path) {
  if (!file.exists(path)) fail()
  con <- file(path, open = "r")
  on.exit(close(con))
  readLines(con, warn = FALSE)
}

split_row <- function(line, k) {
  parts <- strsplit(line, ",", fixed = TRUE)[[1]]
  if (length(parts) != k) fail()
  trimws(parts)
}

qzero <- as.bigq(0L)

fmtq <- function(x) {
  paste0(as.character(numerator(x)), "/", as.character(denominator(x)))
}

main <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  if (length(args) < 1) fail()
  dir <- args[1]

  ulines <- read_lines_strict(file.path(dir, "units.csv"))
  elines <- read_lines_strict(file.path(dir, "edges.csv"))

  # ---- parse units: unit_id,label,value ----
  if (length(ulines) < 1) fail()
  if (trimws(ulines[1]) != "unit_id,label,value") fail()
  urecs <- ulines[-1]
  if (length(urecs) < 1) fail()
  ids <- character(0)
  labs <- integer(0)
  vals <- integer(0)
  for (ln in urecs) {
    if (nchar(ln) == 0) fail()
    f <- split_row(ln, 3)
    uid <- f[1]
    lab <- f[2]
    val <- f[3]
    if (nchar(uid) == 0) fail()
    if (!(lab %in% c("0", "1"))) fail()
    if (!grepl("^-?[0-9]+$", val)) fail()
    ids <- c(ids, uid)
    labs <- c(labs, as.integer(lab))
    vals <- c(vals, as.integer(val))
  }
  if (any(duplicated(ids))) fail()
  n <- length(ids)
  idx <- seq_len(n)
  names(idx) <- ids

  # ---- parse edges (first-order contiguity W1) ----
  if (length(elines) < 1) fail()
  if (trimws(elines[1]) != "unit_i,unit_j") fail()
  erecs <- elines[-1]
  ei <- integer(0)
  ej <- integer(0)
  seen <- character(0)
  for (ln in erecs) {
    if (nchar(ln) == 0) fail()
    f <- split_row(ln, 2)
    a <- f[1]
    b <- f[2]
    if (is.na(idx[a]) || is.na(idx[b])) fail()
    ia <- idx[[a]]
    ib <- idx[[b]]
    if (ia == ib) fail()
    key <- paste(sort(c(ia, ib)), collapse = "-")
    if (key %in% seen) fail()
    seen <- c(seen, key)
    ei <- c(ei, ia)
    ej <- c(ej, ib)
  }
  m <- length(ei)

  # ---- adjacency and second-order contiguity W2 ----
  adj <- vector("list", n)
  for (v in seq_len(n)) adj[[v]] <- integer(0)
  if (m > 0) {
    for (t in seq_len(m)) {
      adj[[ei[t]]] <- c(adj[[ei[t]]], ej[t])
      adj[[ej[t]]] <- c(adj[[ej[t]]], ei[t])
    }
  }
  w2i <- integer(0)
  w2j <- integer(0)
  for (i in seq_len(n)) {
    two <- integer(0)
    for (k in adj[[i]]) two <- c(two, adj[[k]])
    two <- unique(two)
    two <- setdiff(two, c(i, adj[[i]]))
    two <- two[two > i]
    if (length(two) > 0) {
      w2i <- c(w2i, rep.int(i, length(two)))
      w2j <- c(w2j, two)
    }
  }

  # ---- colouring-dependent join-count probabilities (shared by W1 and W2) ----
  n1 <- sum(labs)
  n0 <- n - n1
  bn <- as.bigz(n)
  bn1 <- as.bigz(n1)
  bn0 <- as.bigz(n0)

  falling <- function(a, k) {
    r <- as.bigz(1L)
    for (t in 0:(k - 1)) r <- r * (a - as.bigz(t))
    r
  }
  f2 <- falling(bn, 2)
  f3 <- if (n >= 3) falling(bn, 3) else as.bigz(0L)
  f4 <- if (n >= 4) falling(bn, 4) else as.bigz(0L)

  d2 <- function(num) if (n >= 2) as.bigq(num, f2) else qzero
  d3 <- function(num) if (n >= 3) as.bigq(num, f3) else qzero
  d4 <- function(num) if (n >= 4) as.bigq(num, f4) else qzero

  p <- as.bigq(bn1, bn)
  q <- as.bigq(1L) - p
  free <- list(
    BB = list(p * p, p * p * p, p * p * p * p),
    WW = list(q * q, q * q * q, q * q * q * q),
    BW = list(as.bigq(2L) * p * q, p * q, as.bigq(4L) * p * p * q * q)
  )
  nonfree <- list(
    BB = list(d2(falling(bn1, 2)), d3(falling(bn1, 3)), d4(falling(bn1, 4))),
    WW = list(d2(falling(bn0, 2)), d3(falling(bn0, 3)), d4(falling(bn0, 4))),
    BW = list(
      d2(as.bigz(2L) * bn1 * bn0),
      d3(bn1 * bn0 * (bn - as.bigz(2L))),
      d4(as.bigz(4L) * falling(bn1, 2) * falling(bn0, 2))
    )
  )

  # ---- degree helper for an edge list ----
  degrees <- function(bi, bj) {
    deg <- integer(n)
    if (length(bi) > 0) {
      for (t in seq_len(length(bi))) {
        deg[bi[t]] <- deg[bi[t]] + 1L
        deg[bj[t]] <- deg[bj[t]] + 1L
      }
    }
    deg
  }

  # ---- join-count block for a given weight matrix (edge lists) ----
  block <- function(bi, bj, prefix) {
    mm <- length(bi)
    deg <- degrees(bi, bj)
    s0 <- as.bigz(2L * mm)
    s1 <- as.bigz(4L * mm)
    ssq <- as.bigz(0L)
    for (d in deg) ssq <- ssq + as.bigz(d) * as.bigz(d)
    s2 <- as.bigz(4L) * ssq

    bb <- 0L
    ww <- 0L
    bw <- 0L
    if (mm > 0) {
      for (t in seq_len(mm)) {
        la <- labs[bi[t]]
        lb <- labs[bj[t]]
        if (la == 1L && lb == 1L) {
          bb <- bb + 1L
        } else if (la == 0L && lb == 0L) {
          ww <- ww + 1L
        } else {
          bw <- bw + 1L
        }
      }
    }

    qs2 <- as.bigq(s2)
    qs1 <- as.bigq(s1)
    qs0 <- as.bigq(s0)
    half_s0 <- as.bigq(s0, as.bigz(2L))
    quarter <- as.bigq(1L, 4L)
    coef_m4 <- qs0 * qs0 - qs2 + qs1

    cell <- function(obs, probs) {
      m2 <- probs[[1]]
      m3 <- probs[[2]]
      m4 <- probs[[3]]
      e <- half_s0 * m2
      var <- quarter *
        (qs1 * m2 + (qs2 - as.bigq(2L) * qs1) * m3 + coef_m4 * m4) - e * e
      dev <- as.bigq(obs) - e
      if (var == qzero) {
        lab <- "NA"
      } else if (dev == qzero) {
        lab <- "NS"
      } else if (dev * dev > as.bigq(4L) * var) {
        lab <- if (dev > qzero) "HIGH" else "LOW"
      } else {
        lab <- "NS"
      }
      paste(fmtq(e), fmtq(var), lab)
    }

    c(
      paste0(prefix, "S0 = ", as.character(s0)),
      paste0(prefix, "S1 = ", as.character(s1)),
      paste0(prefix, "S2 = ", as.character(s2)),
      paste0(prefix, "BB = ", bb),
      paste0(prefix, "WW = ", ww),
      paste0(prefix, "BW = ", bw),
      paste0(prefix, "FREE_BB = ", cell(bb, free$BB)),
      paste0(prefix, "FREE_WW = ", cell(ww, free$WW)),
      paste0(prefix, "FREE_BW = ", cell(bw, free$BW)),
      paste0(prefix, "NONFREE_BB = ", cell(bb, nonfree$BB)),
      paste0(prefix, "NONFREE_WW = ", cell(ww, nonfree$WW)),
      paste0(prefix, "NONFREE_BW = ", cell(bw, nonfree$BW))
    )
  }

  # ---- numeric attribute: exact deviations and kurtosis ----
  zbar <- as.bigq(sum(vals), n)
  dvec <- lapply(vals, function(v) as.bigq(v) - zbar)
  m2z <- qzero
  m4z <- qzero
  for (dv in dvec) {
    m2z <- m2z + dv * dv
    m4z <- m4z + dv * dv * dv * dv
  }
  z_defined <- (m2z != qzero)
  b2 <- if (z_defined) as.bigq(n) * m4z / (m2z * m2z) else qzero

  moran_var <- function(qs0, qs1, qs2) {
    if (n < 4) {
      return(NULL)
    }
    s0sq <- qs0 * qs0
    ei <- as.bigq(-1L, n - 1L)
    ei2 <- (as.bigq(n) * ((as.bigq(n * n - 3 * n + 3)) * qs1 - as.bigq(n) * qs2 +
      as.bigq(3L) * s0sq) - b2 * ((as.bigq(n * n - n)) * qs1 -
      as.bigq(2L) * as.bigq(n) * qs2 + as.bigq(6L) * s0sq)) /
      (as.bigq((n - 1) * (n - 2) * (n - 3)) * s0sq)
    ei2 - ei * ei
  }

  geary_var <- function(qs0, qs1, qs2) {
    if (n < 4) {
      return(NULL)
    }
    s0sq <- qs0 * qs0
    (as.bigq(n - 1L) * qs1 * (as.bigq(n * n - 3 * n + 3) - as.bigq(n - 1L) * b2) -
      as.bigq(1L, 4L) * as.bigq(n - 1L) * qs2 *
        (as.bigq(n * n + 3 * n - 6) - as.bigq(n * n - n + 2) * b2) +
      s0sq * (as.bigq(n * n - 3) - as.bigq((n - 1) * (n - 1)) * b2)) /
      (as.bigq(n * (n - 2) * (n - 3)) * s0sq)
  }

  # value line: "value E Var verdict" with NA sentinels for undefined pieces
  num_line <- function(defined, value, e, var_) {
    if (!defined) {
      return("NA NA NA NA")
    }
    if (is.null(var_)) {
      return(paste(fmtq(value), fmtq(e), "NA NA"))
    }
    if (var_ == qzero) {
      lab <- "NA"
    } else {
      dev <- value - e
      if (dev == qzero) {
        lab <- "NS"
      } else if (dev * dev > as.bigq(4L) * var_) {
        lab <- if (dev > qzero) "HIGH" else "LOW"
      } else {
        lab <- "NS"
      }
    }
    paste(fmtq(value), fmtq(e), fmtq(var_), lab)
  }

  # Moran's I and Geary's C on a symmetric binary weight (edge list)
  moran_binary <- function(bi, bj) {
    mm <- length(bi)
    if (!z_defined || mm == 0) {
      return("NA NA NA NA")
    }
    deg <- degrees(bi, bj)
    s0 <- as.bigq(2L * mm)
    s1 <- as.bigq(4L * mm)
    ssq <- as.bigz(0L)
    for (d in deg) ssq <- ssq + as.bigz(d) * as.bigz(d)
    s2 <- as.bigq(as.bigz(4L) * ssq)
    num <- qzero
    for (t in seq_len(mm)) num <- num + dvec[[bi[t]]] * dvec[[bj[t]]]
    num <- as.bigq(2L) * num
    ival <- as.bigq(n) / s0 * num / m2z
    ei <- as.bigq(-1L, n - 1L)
    num_line(TRUE, ival, ei, moran_var(s0, s1, s2))
  }

  geary_binary <- function(bi, bj) {
    mm <- length(bi)
    if (!z_defined || mm == 0) {
      return("NA NA NA NA")
    }
    deg <- degrees(bi, bj)
    s0 <- as.bigq(2L * mm)
    s1 <- as.bigq(4L * mm)
    ssq <- as.bigz(0L)
    for (d in deg) ssq <- ssq + as.bigz(d) * as.bigz(d)
    s2 <- as.bigq(as.bigz(4L) * ssq)
    num <- as.bigz(0L)
    for (t in seq_len(mm)) {
      dd <- as.bigz(vals[bi[t]] - vals[bj[t]])
      num <- num + dd * dd
    }
    num <- as.bigq(as.bigz(2L) * num)
    cval <- as.bigq(n - 1L) / (as.bigq(2L) * s0) * num / m2z
    num_line(TRUE, cval, as.bigq(1L), geary_var(s0, s1, s2))
  }

  # Moran's I on the row-standardized W1 (asymmetric rational weights)
  moran_rowstd <- function() {
    deg <- degrees(ei, ej)
    noniso <- sum(deg > 0)
    if (!z_defined || noniso == 0) {
      return("NA NA NA NA")
    }
    s0 <- as.bigq(noniso)
    # S1 = sum over undirected edges of (1/deg_i + 1/deg_j)^2
    s1 <- qzero
    if (m > 0) {
      for (t in seq_len(m)) {
        wij <- as.bigq(1L, deg[ei[t]]) + as.bigq(1L, deg[ej[t]])
        s1 <- s1 + wij * wij
      }
    }
    # S2 = sum_i (rowsum_i + colsum_i)^2, rowsum_i = 1 (deg>0), colsum_i = sum_{j~i} 1/deg_j
    s2 <- qzero
    for (i in seq_len(n)) {
      rowsum <- if (deg[i] > 0) as.bigq(1L) else qzero
      colsum <- qzero
      for (k in adj[[i]]) colsum <- colsum + as.bigq(1L, deg[k])
      tot <- rowsum + colsum
      s2 <- s2 + tot * tot
    }
    # numerator = sum_i (d_i / deg_i) * sum_{j~i} d_j   (deg_i > 0)
    num <- qzero
    for (i in seq_len(n)) {
      if (deg[i] > 0) {
        nbrsum <- qzero
        for (k in adj[[i]]) nbrsum <- nbrsum + dvec[[k]]
        num <- num + dvec[[i]] * nbrsum / as.bigq(deg[i])
      }
    }
    ival <- as.bigq(n) / s0 * num / m2z
    ei0 <- as.bigq(-1L, n - 1L)
    num_line(TRUE, ival, ei0, moran_var(s0, s1, s2))
  }

  numeric_block <- c(
    paste0("Z_MEAN = ", fmtq(zbar)),
    paste0("Z_SS = ", fmtq(m2z)),
    paste0("MORAN = ", moran_binary(ei, ej)),
    paste0("GEARY = ", geary_binary(ei, ej)),
    paste0("W2_MORAN = ", moran_binary(w2i, w2j)),
    paste0("W2_GEARY = ", geary_binary(w2i, w2j)),
    paste0("STD_MORAN = ", moran_rowstd())
  )

  # ---- exact two-sided conditional-permutation p-values (W1 join counts) ----
  PVAL_CAP <- 20000
  qabs <- function(x) if (x < qzero) -x else x
  perm_pvalues <- function() {
    n1 <- sum(labs == 1L)
    mm <- length(ei)
    obb <- 0L
    oww <- 0L
    obw <- 0L
    if (mm > 0) {
      for (t in seq_len(mm)) {
        la <- labs[ei[t]]
        lb <- labs[ej[t]]
        if (la == 1L && lb == 1L) {
          obb <- obb + 1L
        } else if (la == 0L && lb == 0L) {
          oww <- oww + 1L
        } else {
          obw <- obw + 1L
        }
      }
    }
    tot <- choose(n, n1)
    if (tot > PVAL_CAP) {
      return(c(BB = "NA", WW = "NA", BW = "NA"))
    }
    combs <- combn(n, n1)
    tt <- ncol(combs)
    hb <- new.env()
    hw <- new.env()
    hd <- new.env()
    sb <- 0L
    sw <- 0L
    sd <- 0L
    addv <- function(h, v) {
      k <- as.character(v)
      cur <- h[[k]]
      h[[k]] <- (if (is.null(cur)) 0L else cur) + 1L
    }
    for (cc in seq_len(tt)) {
      isb <- logical(n)
      isb[combs[, cc]] <- TRUE
      bb <- 0L
      ww <- 0L
      bw <- 0L
      if (mm > 0) {
        for (t in seq_len(mm)) {
          a <- isb[ei[t]]
          b <- isb[ej[t]]
          if (a && b) {
            bb <- bb + 1L
          } else if (!a && !b) {
            ww <- ww + 1L
          } else {
            bw <- bw + 1L
          }
        }
      }
      addv(hb, bb)
      addv(hw, ww)
      addv(hd, bw)
      sb <- sb + bb
      sw <- sw + ww
      sd <- sd + bw
    }
    pval <- function(h, ssum, obsv) {
      keys <- ls(h)
      if (length(keys) <= 1) {
        return("NA")
      }
      mu <- as.bigq(ssum, as.bigz(tot))
      thr <- qabs(as.bigq(obsv) - mu)
      cnt <- as.bigz(0L)
      for (k in keys) {
        v <- as.integer(k)
        if (qabs(as.bigq(v) - mu) >= thr) {
          cnt <- cnt + as.bigz(h[[k]])
        }
      }
      fmtq(as.bigq(cnt, as.bigz(tot)))
    }
    c(
      BB = pval(hb, sb, obb),
      WW = pval(hw, sw, oww),
      BW = pval(hd, sd, obw)
    )
  }
  pv <- perm_pvalues()
  pval_lines <- c(
    paste0("PVAL_BB = ", pv["BB"]),
    paste0("PVAL_WW = ", pv["WW"]),
    paste0("PVAL_BW = ", pv["BW"])
  )

  out <- c(
    block(ei, ej, ""), block(w2i, w2j, "W2_"), numeric_block, pval_lines
  )
  cat(paste(out, collapse = "\n"))
  cat("\n")
}

main()
