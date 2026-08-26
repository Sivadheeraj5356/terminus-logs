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
    uw@ ;

: get-amount ( addr -- u )
    0  6 0 do  over 5 i - + c@  swap 8 lshift or  loop  nip ;

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
