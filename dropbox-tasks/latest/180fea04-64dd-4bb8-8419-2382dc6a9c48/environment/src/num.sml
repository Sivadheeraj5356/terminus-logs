(* General purpose numerics. Nothing here knows anything about the study: it is
   quadrature, dense linear algebra, a derivative free minimiser and a bracketed
   root finder, so that none of that has to be rewritten from scratch. *)

signature NUM =
  sig
    val copy : real array -> real array
    val linspace : real * real * int -> real array

    (* cumint (f, h) returns the running integral of f sampled on a uniform
       grid of spacing h, one value per node, starting at 0. Fourth order:
       each panel is integrated with the four point Newton-Cotes rule, so the
       result is exact when f is a cubic. Needs at least 4 samples. *)
    val cumint : real array * real -> real array

    (* nelderMead (f, x0, steps, tol, maxEval) -> (xBest, fBest). steps sets
       the initial simplex edge in each coordinate. Stops when the spread of
       the vertex values falls below tol or the evaluation budget runs out. *)
    val nelderMead : (real array -> real) * real array * real array * real * int
                     -> real array * real

    (* Dense solve and inverse, Gaussian elimination with partial pivoting.
       Raises Fail on a singular matrix. Rows are the outer array. *)
    val luSolve : real array array * real array -> real array
    val inverse : real array array -> real array array

    (* bisect (f, lo, hi, tol, maxIter): f lo and f hi must straddle zero. *)
    val bisect : (real -> real) * real * real * real * int -> real
  end

structure Num :> NUM =
  struct
    fun copy a = Array.tabulate (Array.length a, fn i => Array.sub (a, i))

    fun linspace (lo, hi, n) =
      let val h = (hi - lo) / real n
      in Array.tabulate (n + 1, fn i => lo + real i * h)
      end

    fun cumint (f, h) =
      let
        val n = Array.length f - 1
        val _ = if n < 3 then raise Fail "cumint: need at least 4 samples" else ()
        fun g i = Array.sub (f, i)
        val w = h / 24.0
        val inc = Array.tabulate (n + 1, fn i =>
          if i = 0 then 0.0
          else if i = 1 then w * (9.0 * g 0 + 19.0 * g 1 - 5.0 * g 2 + g 3)
          else if i < n then
            w * (~(g (i - 2)) + 13.0 * g (i - 1) + 13.0 * g i - g (i + 1))
          else
            w * (g (n - 3) - 5.0 * g (n - 2) + 19.0 * g (n - 1) + 9.0 * g n))
        val out = Array.array (n + 1, 0.0)
        fun run (i, acc) =
          if i > n then ()
          else
            let val v = acc + Array.sub (inc, i)
            in Array.update (out, i, v); run (i + 1, v)
            end
      in
        run (0, 0.0); out
      end

    fun nelderMead (f, x0, steps, tol, maxEval) =
      let
        val n = Array.length x0
        val evals = ref 0
        fun fe x = (evals := !evals + 1; f x)
        (* simplex as a mutable array of (point, value) *)
        val verts = Array.tabulate (n + 1, fn i =>
          let
            val p = copy x0
            val _ = if i > 0 then
                      Array.update (p, i - 1,
                                    Array.sub (p, i - 1) + Array.sub (steps, i - 1))
                    else ()
          in (p, fe p)
          end)
        fun value i = #2 (Array.sub (verts, i))
        fun point i = #1 (Array.sub (verts, i))
        (* insertion sort by value; the simplex has only n+1 vertices *)
        fun sortVerts () =
          let
            fun place i =
              if i > n then ()
              else
                let
                  val v = Array.sub (verts, i)
                  fun down j =
                    if j > 0 andalso #2 (Array.sub (verts, j - 1)) > #2 v then
                      (Array.update (verts, j, Array.sub (verts, j - 1));
                       down (j - 1))
                    else Array.update (verts, j, v)
                in
                  down i; place (i + 1)
                end
          in
            place 1
          end
        val _ = sortVerts ()
        fun combine (a, b, t) =
          Array.tabulate (n, fn i =>
            Array.sub (a, i) + t * (Array.sub (b, i) - Array.sub (a, i)))
        fun centroid () =
          Array.tabulate (n, fn i =>
            let
              fun add (j, acc) =
                if j >= n then acc else add (j + 1, acc + Array.sub (point j, i))
            in add (0, 0.0) / real n
            end)
        fun spread () = Real.abs (value n - value 0)
        fun loop () =
          if !evals > maxEval orelse spread () < tol then ()
          else
            let
              val c = centroid ()
              val xw = point n
              val xr = combine (xw, c, 2.0)          (* reflect through c *)
              val fr = fe xr
            in
              if fr < value 0 then
                let
                  val xe = combine (xw, c, 3.0)      (* expand *)
                  val fe' = fe xe
                in
                  Array.update (verts, n, if fe' < fr then (xe, fe') else (xr, fr));
                  sortVerts (); loop ()
                end
              else if fr < value (n - 1) then
                (Array.update (verts, n, (xr, fr)); sortVerts (); loop ())
              else
                let
                  val xc = combine (xw, c, 0.5)      (* contract *)
                  val fc = fe xc
                in
                  if fc < value n then
                    (Array.update (verts, n, (xc, fc)); sortVerts (); loop ())
                  else
                    let
                      val x0b = point 0
                      fun shrink i =
                        if i > n then ()
                        else
                          let val p = combine (point i, x0b, 0.5)
                          in Array.update (verts, i, (p, fe p)); shrink (i + 1)
                          end
                    in
                      shrink 1; sortVerts (); loop ()
                    end
                end
            end
        val _ = loop ()
      in
        (copy (point 0), value 0)
      end

    fun luSolve (a0, b0) =
      let
        val n = Array.length b0
        val a = Array.tabulate (n, fn i => copy (Array.sub (a0, i)))
        val b = copy b0
        fun swap (i, j) =
          if i = j then ()
          else
            let
              val t = Array.sub (a, i)
              val tb = Array.sub (b, i)
            in
              Array.update (a, i, Array.sub (a, j)); Array.update (a, j, t);
              Array.update (b, i, Array.sub (b, j)); Array.update (b, j, tb)
            end
        fun pivot k =
          let
            fun best (i, bi, bv) =
              if i >= n then bi
              else
                let val v = Real.abs (Array.sub (Array.sub (a, i), k))
                in if v > bv then best (i + 1, i, v) else best (i + 1, bi, bv)
                end
          in best (k, k, Real.abs (Array.sub (Array.sub (a, k), k)))
          end
        fun elim k =
          if k >= n then ()
          else
            let
              val _ = swap (k, pivot k)
              val akk = Array.sub (Array.sub (a, k), k)
              val _ = if Real.abs akk < 1.0E~300 then raise Fail "luSolve: singular"
                      else ()
              fun row i =
                if i >= n then ()
                else
                  let
                    val m = Array.sub (Array.sub (a, i), k) / akk
                    fun col j =
                      if j >= n then ()
                      else
                        (Array.update (Array.sub (a, i), j,
                           Array.sub (Array.sub (a, i), j)
                           - m * Array.sub (Array.sub (a, k), j));
                         col (j + 1))
                  in
                    col k;
                    Array.update (b, i, Array.sub (b, i) - m * Array.sub (b, k));
                    row (i + 1)
                  end
            in row (k + 1); elim (k + 1)
            end
        val _ = elim 0
        val x = Array.array (n, 0.0)
        fun back i =
          if i < 0 then ()
          else
            let
              fun acc (j, s) =
                if j >= n then s
                else acc (j + 1, s + Array.sub (Array.sub (a, i), j)
                                     * Array.sub (x, j))
              val s = acc (i + 1, 0.0)
            in
              Array.update (x, i,
                (Array.sub (b, i) - s) / Array.sub (Array.sub (a, i), i));
              back (i - 1)
            end
      in
        back (n - 1); x
      end

    fun inverse a =
      let
        val n = Array.length a
        val cols = List.tabulate (n, fn j =>
          luSolve (a, Array.tabulate (n, fn i => if i = j then 1.0 else 0.0)))
        val colA = Array.fromList cols
      in
        Array.tabulate (n, fn i =>
          Array.tabulate (n, fn j => Array.sub (Array.sub (colA, j), i)))
      end

    fun bisect (f, lo0, hi0, tol, maxIter) =
      let
        val flo = f lo0
        val fhi = f hi0
        val _ = if flo * fhi > 0.0 then raise Fail "bisect: root not bracketed"
                else ()
        fun loop (lo, hi, flo, k) =
          if k >= maxIter orelse (hi - lo) < tol then 0.5 * (lo + hi)
          else
            let
              val mid = 0.5 * (lo + hi)
              val fm = f mid
            in
              if Real.== (fm, 0.0) then mid
              else if flo * fm < 0.0 then loop (lo, mid, flo, k + 1)
              else loop (mid, hi, fm, k + 1)
            end
      in
        loop (lo0, hi0, flo, 0)
      end
  end
