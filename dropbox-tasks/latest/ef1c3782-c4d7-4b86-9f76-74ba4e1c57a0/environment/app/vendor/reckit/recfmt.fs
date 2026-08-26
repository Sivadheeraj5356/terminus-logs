\ recfmt -- field accessors for the clearing-tape posting record.
\
\ The interchange record is a fixed eight-byte frame laid out exactly as the
\ vendored FORMAT descriptor records it: a two-byte ledger key at offset 0 and a
\ six-byte posting amount at offset 2. These are the reference accessors: given
\ the base address of a record frame they return the ledger key and the amount
\ as they are meant to be read from the tape. Any tool that reports over the
\ vendored tape is expected to take its field values from here rather than
\ reaching into the frame on its own.

: fld-ledger ( addr -- u )
    dup c@ 8 lshift  swap 1+ c@ or ;

: fld-amount ( addr -- u )
    0  6 0 do  over i + c@  swap 8 lshift or  loop  nip ;
