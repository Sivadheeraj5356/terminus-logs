(* Reference analysis: Laplace-marginal fit of the folding landscape.

   Layout:
     - load the study out of SQLite
     - build a landscape kernel per (c2, cs) and read rates off it
     - inner conditional mode over (a_m, b_m), a profiled out in closed form
     - outer search on the Laplace-marginal objective F(theta)
     - marginal standard errors, the cs deviance, and the derived physics *)

structure Fold =
  struct
    val NG = 250              (* quadrature panels; theta* is converged by ~250 *)
    val LOG2PI = Math.ln (2.0 * Math.pi)

    (* ---------------- study ---------------- *)

    fun getReal (row, i) =
      case Real.fromString (List.nth (row, i)) of
        SOME v => v
      | NONE => raise Fail ("could not parse a real from: " ^ List.nth (row, i))

    fun loadConfig dbPath : Types.config =
      let
        val sql = "SELECT c4, c1, xd, wd, kt, xlo, xhi, xau, xaf FROM config"
      in
        case Db.query dbPath sql of
          [row] =>
            { c4 = getReal (row, 0), c1 = getReal (row, 1),
              xd = getReal (row, 2), wd = getReal (row, 3),
              kT = getReal (row, 4), xlo = getReal (row, 5),
              xhi = getReal (row, 6), xau = getReal (row, 7),
              xaf = getReal (row, 8) }
        | _ => raise Fail "config table should hold exactly one row"
      end

    fun loadInit dbPath =
      let
        val sql = "SELECT init_c2, init_cs, init_log_d, init_sigma_a, \
                  \init_sigma_b, init_sigma_e FROM config"
      in
        case Db.query dbPath sql of
          [row] => Array.tabulate (6, fn i => getReal (row, i))
        | _ => raise Fail "config table should hold exactly one row"
      end

    fun loadMolecules dbPath : Types.molecule list =
      let
        val ids = List.map (fn r => case Int.fromString (List.hd r) of
                                      SOME i => i
                                    | NONE => raise Fail "bad molecule id")
                           (Db.query dbPath "SELECT id FROM molecules ORDER BY id")
        fun one id =
          let
            val sql = "SELECT force_pn, log_k_unfold, log_k_fold FROM \
                      \observations WHERE molecule_id = " ^ Int.toString id
                      ^ " ORDER BY rowid"
            val rows = Db.query dbPath sql
            val v = Array.fromList rows
            val nj = Array.length v
            val _ = if nj = 0 then raise Fail ("molecule with no rows: "
                                               ^ Int.toString id) else ()
          in
            { id = id,
              force = Array.tabulate (nj, fn j => getReal (Array.sub (v, j), 0)),
              logKu = Array.tabulate (nj, fn j => getReal (Array.sub (v, j), 1)),
              logKf = Array.tabulate (nj, fn j => getReal (Array.sub (v, j), 2)) }
          end
      in
        List.map one ids
      end

    (* ---------------- landscape and rates ---------------- *)

    (* The zero force profile does not depend on the force, so exp(U0) and
       exp(-U0) are built once per (c2, cs) and reused for every molecule and
       every clamp force. The force only contributes exp(-s*x), which on a
       uniform grid is a geometric sequence: one exp instead of one per node. *)
    type kernel = { x : real array, eu0 : real array, emu0 : real array,
                    lo : real, h : real, n : int }

    fun mkKernel (cfg : Types.config, c2, cs, lo, hi, n) : kernel =
      let
        val x = Num.linspace (lo, hi, n)
        val h = (hi - lo) / real n
        val u0 = Array.tabulate (n + 1, fn i =>
          let
            val xi = Array.sub (x, i)
            val d = (xi - #xd cfg) / #wd cfg
          in
            #c4 cfg * xi * xi * xi * xi - c2 * xi * xi + #c1 cfg * xi
            + cs * Math.exp (~0.5 * d * d)
          end)
      in
        { x = x,
          eu0 = Array.tabulate (n + 1, fn i => Math.exp (Array.sub (u0, i))),
          emu0 = Array.tabulate (n + 1, fn i => Math.exp (~(Array.sub (u0, i)))),
          lo = lo, h = h, n = n }
      end

    (* exp(U_F) and exp(-U_F) on the grid, from the cached profile *)
    fun tilted (kern : kernel, s) =
      let
        val {eu0, emu0, lo, h, n, ...} = kern
        val np1 = n + 1
        val r = Math.exp (~s * h)
        val t0 = Math.exp (~s * lo)
        val tilt = Array.array (np1, t0)
        fun fill i =
          if i > n then ()
          else (Array.update (tilt, i, Array.sub (tilt, i - 1) * r); fill (i + 1))
        val _ = fill 1
        val ep = Array.tabulate (np1, fn i =>
          Array.sub (eu0, i) * Array.sub (tilt, i))
        val em = Array.tabulate (np1, fn i =>
          Array.sub (emu0, i) / Array.sub (tilt, i))
      in
        (ep, em)
      end

    fun kernelU (cfg, c2, cs) =
      mkKernel (cfg, c2, cs, #xlo cfg, #xau cfg, NG)
    fun kernelF (cfg, c2, cs) =
      mkKernel (cfg, c2, cs, #xaf cfg, #xhi cfg, NG)

    (* T0 only: log k without derivatives *)
    fun logRate (kern : kernel, fromLeft, s, logD) =
      let
        val {h, n, ...} = kern
        val np1 = n + 1
        val (ep, em) = tilted (kern, s)
        val c = Num.cumint (em, h)
        val C0 = if fromLeft then c
                 else let val t = Array.sub (c, n)
                      in Array.tabulate (np1, fn i => t - Array.sub (c, i)) end
        val prod = Array.tabulate (np1, fn i => Array.sub (ep, i) * Array.sub (C0, i))
        val T0 = Array.sub (Num.cumint (prod, h), n)
      in
        logD - Math.ln T0
      end

    (* log k together with its first and second derivative in s = F/kT *)
    fun logRateD (kern : kernel, fromLeft, s, logD) =
      let
        val {x, h, n, ...} = kern
        val np1 = n + 1
        val (ep, em) = tilted (kern, s)
        fun inner w =
          let
            val f = Array.tabulate (np1, fn i => Array.sub (em, i) * w i)
            val c = Num.cumint (f, h)
          in
            if fromLeft then c
            else let val t = Array.sub (c, n)
                 in Array.tabulate (np1, fn i => t - Array.sub (c, i)) end
          end
        val C0 = inner (fn _ => 1.0)
        val C1 = inner (fn i => Array.sub (x, i))
        val C2 = inner (fn i => let val xi = Array.sub (x, i) in xi * xi end)
        fun outer w =
          Array.sub (Num.cumint (Array.tabulate (np1, fn i =>
            Array.sub (ep, i) * w i), h), n)
        val T0 = outer (fn i => Array.sub (C0, i))
        val T1 = outer (fn i =>
          ~(Array.sub (x, i)) * Array.sub (C0, i) + Array.sub (C1, i))
        val T2 = outer (fn i =>
          let val xi = Array.sub (x, i)
          in xi * xi * Array.sub (C0, i) - 2.0 * xi * Array.sub (C1, i)
             + Array.sub (C2, i)
          end)
        val r1 = T1 / T0
        val r2 = T2 / T0
      in
        (logD - Math.ln T0, ~r1, r1 * r1 - r2)
      end

    (* ---------------- inner conditional mode ---------------- *)

    (* For molecule m at nominal force F the effective s is F*exp(b)/kT, so
       ds/db = s and d2s/db2 = s. *)
    fun molBlocks (cfg : Types.config, ku, kf, mol : Types.molecule, th, b) =
      let
        val c2 = Array.sub (th, 0)
        val logD = Array.sub (th, 2)
        val sa = Array.sub (th, 3)
        val sb = Array.sub (th, 4)
        val se = Array.sub (th, 5)
        val ive2 = 1.0 / (se * se)
        val iva2 = 1.0 / (sa * sa)
        val ivb2 = 1.0 / (sb * sb)
        val nj = Array.length (#force mol)
        val eb = Math.exp b
        (* per observation: g, dg/db, d2g/db2 for both channels *)
        val gu = Array.array (nj, 0.0) and du = Array.array (nj, 0.0)
        and eu = Array.array (nj, 0.0)
        val gf = Array.array (nj, 0.0) and df = Array.array (nj, 0.0)
        and ef = Array.array (nj, 0.0)
        fun fill j =
          if j >= nj then ()
          else
            let
              val s = Array.sub (#force mol, j) * eb / #kT cfg
              val (g1, a1, b1) = logRateD (ku, true, s, logD)
              val (g2, a2, b2) = logRateD (kf, false, s, logD)
            in
              Array.update (gu, j, g1);
              Array.update (du, j, a1 * s);
              Array.update (eu, j, b1 * s * s + a1 * s);
              Array.update (gf, j, g2);
              Array.update (df, j, a2 * s);
              Array.update (ef, j, b2 * s * s + a2 * s);
              fill (j + 1)
            end
        val _ = fill 0
        (* a has a closed form at the mode of the joint density *)
        fun sumOver (y, g) =
          let
            fun go (j, acc) =
              if j >= nj then acc
              else go (j + 1, acc + Array.sub (y, j) - Array.sub (g, j))
          in go (0, 0.0)
          end
        val a = (sumOver (#logKu mol, gu) + sumOver (#logKf mol, gf))
                / (2.0 * real nj + se * se / (sa * sa))
        val ru = Array.tabulate (nj, fn j =>
          Array.sub (#logKu mol, j) - a - Array.sub (gu, j))
        val rf = Array.tabulate (nj, fn j =>
          Array.sub (#logKf mol, j) - a - Array.sub (gf, j))
        fun acc f = let fun go (j, s) = if j >= nj then s else go (j + 1, s + f j)
                    in go (0, 0.0) end
        val Haa = 2.0 * real nj * ive2 + iva2
        val Hab = acc (fn j => Array.sub (du, j) + Array.sub (df, j)) * ive2
        val Hbb = acc (fn j =>
                    Array.sub (du, j) * Array.sub (du, j)
                    - Array.sub (ru, j) * Array.sub (eu, j)
                    + Array.sub (df, j) * Array.sub (df, j)
                    - Array.sub (rf, j) * Array.sub (ef, j)) * ive2 + ivb2
        val gb = ~(acc (fn j => Array.sub (ru, j) * Array.sub (du, j)
                                + Array.sub (rf, j) * Array.sub (df, j))) * ive2
                 + b * ivb2
        val quad = 0.5 * acc (fn j =>
                     Array.sub (ru, j) * Array.sub (ru, j)
                     + Array.sub (rf, j) * Array.sub (rf, j)) * ive2
                   + 0.5 * a * a * iva2 + 0.5 * b * b * ivb2
      in
        { a = a, Haa = Haa, Hab = Hab, Hbb = Hbb, gb = gb, quad = quad }
      end

    fun molMode (cfg, ku, kf, mol, th, b0) =
      let
        fun loop (b, it) =
          if it > 60 then b
          else
            let
              val r = molBlocks (cfg, ku, kf, mol, th, b)
              val cur = #Hbb r - #Hab r * #Hab r / #Haa r
              val cur = if cur > 1.0E~10 then cur else 1.0
              val st0 = ~(#gb r) / cur
              val st = if st0 > 0.4 then 0.4 else if st0 < ~0.4 then ~0.4 else st0
              val b' = b + st
            in
              if Real.abs st < 1.0E~12 then b' else loop (b', it + 1)
            end
      in
        loop (b0, 0)
      end

    (* ---------------- the marginal objective ---------------- *)

    fun objective (cfg, mols : Types.molecule list, th, warm : real array) =
      let
        val c2 = Array.sub (th, 0)
        val cs = Array.sub (th, 1)
        val sa = Array.sub (th, 3)
        val sb = Array.sub (th, 4)
        val se = Array.sub (th, 5)
      in
        if sa <= 0.0 orelse sb <= 0.0 orelse se <= 0.0 orelse c2 <= 0.0 then
          1.0E100
        else
          let
            val ku = kernelU (cfg, c2, cs)
            val kf = kernelF (cfg, c2, cs)
            val M = List.length mols
            val K = List.foldl (fn (m, s) => s + 2 * Array.length (#force m)) 0 mols
            fun go ([], _, accQ, accL, ok) = (accQ, accL, ok)
              | go (m :: rest, i, accQ, accL, ok) =
                  let
                    val b = molMode (cfg, ku, kf, m, th, Array.sub (warm, i))
                    val _ = Array.update (warm, i, b)
                    val r = molBlocks (cfg, ku, kf, m, th, b)
                    val det = #Haa r * #Hbb r - #Hab r * #Hab r
                  in
                    if det <= 0.0 orelse Real.isNan det then
                      (accQ, accL, false)
                    else
                      go (rest, i + 1, accQ + #quad r, accL + Math.ln det, ok)
                  end
            val (quad, logdet, ok) = go (mols, 0, 0.0, 0.0, true)
          in
            if not ok then 1.0E100
            else
              let
                val Jhat = quad + real K * Math.ln se + 0.5 * real K * LOG2PI
                           + real M * Math.ln sa + real M * Math.ln sb
                           + real M * LOG2PI
                val v = Jhat + 0.5 * logdet - real M * LOG2PI
              in
                if Real.isNan v then 1.0E100 else v
              end
          end
      end

    (* theta is searched in z = (ln c2, cs, logD, ln sa, ln sb, ln se) *)
    fun toZ th = Array.fromList
      [Math.ln (Array.sub (th, 0)), Array.sub (th, 1), Array.sub (th, 2),
       Math.ln (Array.sub (th, 3)), Math.ln (Array.sub (th, 4)),
       Math.ln (Array.sub (th, 5))]

    fun fromZ z = Array.fromList
      [Math.exp (Array.sub (z, 0)), Array.sub (z, 1), Array.sub (z, 2),
       Math.exp (Array.sub (z, 3)), Math.exp (Array.sub (z, 4)),
       Math.exp (Array.sub (z, 5))]

    (* Minimise F. csFixed = SOME v clamps cs and searches the other five. *)
    fun search (cfg, mols, th0, csFixed) =
      let
        val M = List.length mols
        val warm = Array.array (M, 0.0)
        val free = case csFixed of NONE => [0, 1, 2, 3, 4, 5] | SOME _ => [0, 2, 3, 4, 5]
        val nf = List.length free
        val z0 = toZ th0
        fun expand zf =
          let
            val z = Num.copy z0
            val _ = List.foldl (fn (i, k) =>
                      (Array.update (z, i, Array.sub (zf, k)); k + 1)) 0 free
            val th = fromZ z
          in
            case csFixed of NONE => th
                          | SOME v => (Array.update (th, 1, v); th)
          end
        fun obj zf = objective (cfg, mols, expand zf, warm)
        fun runFrom (zf, step, tol, budget) =
          Num.nelderMead (obj, zf, Array.array (nf, step), tol, budget)
        val base = Array.fromList (List.map (fn i => Array.sub (z0, i)) free)
        (* F is unimodal here, so a short restart ladder from the stored guess
           plus one displaced start is enough to pin the interior minimum. *)
        fun oneStart shift =
          let
            val z = Num.copy base
            val _ = Array.update (z, 0, Array.sub (z, 0) + shift)
            val (z1, _) = runFrom (z, 0.06, 1.0E~10, 6000)
            val (z2, f2) = runFrom (z1, 0.006, 1.0E~13, 6000)
          in
            (z2, f2)
          end
        val cands = List.map oneStart [0.0, 0.16]
        val best = List.foldl (fn ((z, f), (bz, bf)) =>
                     if f < bf then (z, f) else (bz, bf))
                   (hd cands) (tl cands)
      in
        (expand (#1 best), #2 best)
      end

    (* ---------------- standard errors ---------------- *)

    fun hessianTheta (cfg, mols, th) =
      let
        val warm = Array.array (List.length mols, 0.0)
        fun f t = objective (cfg, mols, t, warm)
        fun step i =
          let val v = Real.abs (Array.sub (th, i))
          in (if v > 1.0E~3 then v else 1.0E~3) * 1.0E~4
          end
        fun shift (i, si, j, sj) =
          let
            val t = Num.copy th
            val _ = Array.update (t, i, Array.sub (t, i) + si * step i)
            val _ = Array.update (t, j, Array.sub (t, j) + sj * step j)
          in f t
          end
        val f0 = f th
        val H = Array.tabulate (6, fn _ => Array.array (6, 0.0))
        fun fill (i, j) =
          if i >= 6 then ()
          else if j >= 6 then fill (i + 1, i + 1)
          else
            let
              val v =
                if i = j then
                  (shift (i, 1.0, i, 0.0) - 2.0 * f0 + shift (i, ~1.0, i, 0.0))
                  / (step i * step i)
                else
                  (shift (i, 1.0, j, 1.0) - shift (i, 1.0, j, ~1.0)
                   - shift (i, ~1.0, j, 1.0) + shift (i, ~1.0, j, ~1.0))
                  / (4.0 * step i * step j)
            in
              Array.update (Array.sub (H, i), j, v);
              Array.update (Array.sub (H, j), i, v);
              fill (i, j + 1)
            end
        val _ = fill (0, 0)
      in
        H
      end

    (* ---------------- derived physics ---------------- *)

    fun derived (cfg : Types.config, th) =
      let
        val c2 = Array.sub (th, 0)
        val cs = Array.sub (th, 1)
        val logD = Array.sub (th, 2)
        val ku = kernelU (cfg, c2, cs)
        val kf = kernelF (cfg, c2, cs)
        fun gap F =
          logRate (ku, true, F / #kT cfg, logD)
          - logRate (kf, false, F / #kT cfg, logD)
        val fHalf = Num.bisect (gap, 0.05, 30.0, 1.0E~11, 200)
        val lkf0 = logRate (kf, false, 0.0, logD)
      in
        (fHalf, lkf0)
      end

    (* ---------------- top level ---------------- *)

    fun run (dbPath : string) : Types.result =
      let
        val cfg = loadConfig dbPath
        val th0 = loadInit dbPath
        val mols = loadMolecules dbPath
        val (th, F) = search (cfg, mols, th0, NONE)
        val H = hessianTheta (cfg, mols, th)
        val C = Num.inverse H
        fun se i = Math.sqrt (Array.sub (Array.sub (C, i), i))
        (* constrained refit at cs = 0 for the likelihood ratio *)
        val th0c = Num.copy th
        val _ = Array.update (th0c, 1, 0.0)
        val (_, Fc) = search (cfg, mols, th0c, SOME 0.0)
        val (fHalf, lkf0) = derived (cfg, th)
      in
        { c2 = Array.sub (th, 0), cs = Array.sub (th, 1),
          logD = Array.sub (th, 2), sigmaA = Array.sub (th, 3),
          sigmaB = Array.sub (th, 4), sigmaE = Array.sub (th, 5),
          seC2 = se 0, seCs = se 1, seLogD = se 2,
          devCs = 2.0 * (Fc - F), fHalf = fHalf, logKFoldZero = lkf0 }
      end
  end
