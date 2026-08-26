(* The analysis lives here. Fold.run is handed the path of a study database and
   must return the completed report record; main.sml serialises whatever it
   returns. loadConfig below is a worked example of the query and parse pattern
   used throughout the rest of the schema. *)

structure Fold =
  struct
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

    fun run (dbPath : string) : Types.result =
      let
        val _ = loadConfig dbPath
      in
        raise Fail "Fold.run is not implemented"
      end
  end
