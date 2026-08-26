(* Shared record types. The field names of Types.result fix the keys of the
   emitted JSON (main.sml walks this record), so the report schema is not
   something to invent. *)

structure Types =
  struct
    (* The fixed constants of one study, as held in the config table:
       quartic stiffness, native bias, desolvation centre and width, thermal
       energy, and the four landscape boundaries. *)
    type config =
      { c4 : real, c1 : real, xd : real, wd : real, kT : real,
        xlo : real, xhi : real, xau : real, xaf : real }

    (* One molecule: its identifier, the clamp forces it was held at, and the
       unfolding and folding log rates measured at each of those forces. *)
    type molecule =
      { id : int, force : real array, logKu : real array, logKf : real array }

    type result =
      { c2 : real, cs : real, logD : real,
        sigmaA : real, sigmaB : real, sigmaE : real,
        seC2 : real, seCs : real, seLogD : real,
        devCs : real, fHalf : real, logKFoldZero : real }
  end
