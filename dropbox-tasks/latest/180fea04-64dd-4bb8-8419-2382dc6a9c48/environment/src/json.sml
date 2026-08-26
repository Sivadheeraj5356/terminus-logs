(* Minimal JSON emitter. SML prints negative numbers with a leading tilde and
   exponents with a capital E, neither of which JSON accepts, so every real
   goes through realStr. *)

signature JSON =
  sig
    val realStr : real -> string
    val obj : (string * string) list -> string
    val num : string * real -> string * string
  end

structure Json :> JSON =
  struct
    fun realStr x =
      if Real.isNan x then "null"
      else if not (Real.isFinite x) then "null"
      else
        let
          val s = Real.fmt (StringCvt.GEN (SOME 17)) x
          fun fix #"~" = "-"
            | fix #"E" = "e"
            | fix c = String.str c
        in
          String.translate fix s
        end

    fun num (k, v) = (k, realStr v)

    fun obj fields =
      let
        fun one (k, v) = String.concat ["  \"", k, "\": ", v]
      in
        String.concat
          ["{\n", String.concatWith ",\n" (List.map one fields), "\n}\n"]
      end
  end
