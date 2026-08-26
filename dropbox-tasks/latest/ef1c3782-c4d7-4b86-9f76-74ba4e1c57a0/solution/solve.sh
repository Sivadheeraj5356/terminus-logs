#!/bin/bash
set -euo pipefail

# The assembled tool reads each record frame's fields itself with the machine's
# native cell fetches instead of taking them from the vendored recfmt library.
# The tape frames are laid out most-significant byte first, so native reads
# transpose the bytes of every multi-byte field: harmless on the small shipped
# tape, whose field bytes happen to be symmetric, and silently wrong on any
# frame whose bytes are not. Route both field reads through the vendored
# accessors (fld-ledger and fld-amount) so the amounts are the ones recfmt reads
# from the frame, then rebuild. The vendored kit is left untouched.

cat > /app/build/decode.fs <<'DECODE_FS'
\ decode.fs -- walk the clearing tape and write the postings report.
\
\ For each record frame the report writes a line of the ledger key and the
\ posting amount separated by a tab, and after the last frame a final line whose
\ key is TOTAL carrying the summed amount. Input and output paths come from the
\ command line; with none it reads /app/data/records.bin and writes
\ /app/data/report.txt.

2variable in-path  2variable out-path  2variable src
variable ofid
create tabbuf  9 c,
create nlbuf  10 c,

: wstr ( c-addr u -- ) ofid @ write-file throw ;
: wtab ( -- ) tabbuf 1 wstr ;
: wnl  ( -- ) nlbuf 1 wstr ;
: wnum ( u -- ) 0 <# #s #> wstr ;

: get-args
    next-arg dup if in-path 2! else 2drop s" /app/data/records.bin" in-path 2! then
    next-arg dup if out-path 2! else 2drop s" /app/data/report.txt" out-path 2! then ;

: get-ledger ( addr -- u )
    fld-ledger ;

: get-amount ( addr -- u )
    fld-amount ;

: nrec ( -- n ) src 2@ nip 8 / ;
: rec  ( i -- addr ) 8 * src 2@ drop + ;

: main
    get-args
    in-path 2@ slurp-file src 2!
    out-path 2@ w/o create-file throw ofid !
    0
    nrec 0 ?do
        i rec
        dup get-ledger  swap 2 + get-amount
        >r
        wnum wtab  r@ wnum wnl
        r> +
    loop
    s" TOTAL" wstr wtab wnum wnl
    ofid @ close-file throw ;

main bye
DECODE_FS

bash /app/build/run.sh
