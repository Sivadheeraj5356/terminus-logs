(* Thin read-only SQLite access. Shells out to the sqlite3 CLI and parses the
   tab separated rows it prints. Provided so that reading the study is not the
   interesting part of the exercise. *)

signature DB =
  sig
    (* query dbPath sql -> one string list per result row, columns in
       SELECT order. Empty result set gives []. Raises Fail on any sqlite
       error or if the CLI cannot be reached. *)
    val query : string -> string -> string list list

    (* Convenience wrappers over query for single valued lookups. *)
    val queryReal : string -> string -> real
    val queryInt : string -> string -> int
  end

structure Db :> DB =
  struct
    fun shellQuote s =
      let
        fun esc #"'" = "'\\''"
          | esc c = String.str c
      in
        "'" ^ String.translate esc s ^ "'"
      end

    fun readAll path =
      let
        val ins = TextIO.openIn path
      in
        (TextIO.inputAll ins before TextIO.closeIn ins)
        handle e => (TextIO.closeIn ins; raise e)
      end

    fun splitTabs line =
      String.fields (fn c => c = #"\t") line

    fun query dbPath sql =
      let
        val tmp = OS.FileSys.tmpName ()
        (* the CLI takes the separator literally, so this has to be a real tab *)
        val cmd = String.concat
                    ["sqlite3 -noheader -separator '\t' ",
                     shellQuote dbPath, " ", shellQuote sql, " > ",
                     shellQuote tmp, " 2>/dev/null"]
        val status = OS.Process.system cmd
        val _ = if OS.Process.isSuccess status then ()
                else (OS.FileSys.remove tmp handle _ => ();
                      raise Fail ("sqlite3 failed for query: " ^ sql))
        val text = readAll tmp
        val _ = OS.FileSys.remove tmp handle _ => ()
        val lines = List.filter (fn l => l <> "")
                                (String.fields (fn c => c = #"\n") text)
      in
        List.map splitTabs lines
      end

    fun queryReal dbPath sql =
      case query dbPath sql of
        [[v]] => (case Real.fromString v of
                    SOME r => r
                  | NONE => raise Fail ("not a real: " ^ v))
      | _ => raise Fail ("expected one value from: " ^ sql)

    fun queryInt dbPath sql =
      case query dbPath sql of
        [[v]] => (case Int.fromString v of
                    SOME i => i
                  | NONE => raise Fail ("not an int: " ^ v))
      | _ => raise Fail ("expected one value from: " ^ sql)
  end
