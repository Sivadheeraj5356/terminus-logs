(* Entry point: takes the study database and the report path, hands the work to
   Fold.run and writes the record out as JSON. *)

structure Main =
  struct
    fun usage () =
      (TextIO.output (TextIO.stdErr,
         "usage: folding <study.sqlite> <report.json>\n");
       OS.Process.exit OS.Process.failure)

    fun emit (outPath, r : Types.result) =
      let
        val fields = List.map Json.num
          [("c2", #c2 r),
           ("cs", #cs r),
           ("log_d", #logD r),
           ("sigma_a", #sigmaA r),
           ("sigma_b", #sigmaB r),
           ("sigma_e", #sigmaE r),
           ("se_c2", #seC2 r),
           ("se_cs", #seCs r),
           ("se_log_d", #seLogD r),
           ("dev_cs", #devCs r),
           ("f_half", #fHalf r),
           ("log_k_fold_zero", #logKFoldZero r)]
        val outs = TextIO.openOut outPath
      in
        TextIO.output (outs, Json.obj fields);
        TextIO.closeOut outs
      end

    fun main () =
      case CommandLine.arguments () of
        [dbPath, outPath] => emit (outPath, Fold.run dbPath)
      | _ => usage ()
  end

val _ = Main.main ()
