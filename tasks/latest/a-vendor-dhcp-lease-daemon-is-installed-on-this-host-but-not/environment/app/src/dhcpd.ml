(* DHCP-style IPv4 lease allocation manager.
   A self-contained OCaml command-line program: it reads one JSON request from the
   file named on the command line, applies the operation named by that request's
   "op" field, and writes one JSON result on standard output with a "code" field.
   All lease and CIDR arithmetic is OCaml; jq only pulls fields out of the request
   JSON and sqlite3 only persists state. *)

let getenv k = try Sys.getenv k with Not_found -> ""

(* The operational state lives in the service account's spool directory; the
   administrator points the tools at it through the DHCPD_DB environment
   variable, which keeps the live database and any throwaway one apart. *)
let db_path = match getenv "DHCPD_DB" with "" -> "/var/lib/dhcpd/dhcp.db" | p -> p

let read_all ic =
  let buf = Buffer.create 1024 in
  let chunk = Bytes.create 4096 in
  let rec loop () =
    let n = input ic chunk 0 4096 in
    if n > 0 then (Buffer.add_subbytes buf chunk 0 n; loop ())
  in
  loop (); Buffer.contents buf

let run_read cmd =
  let ic = Unix.open_process_in cmd in
  let out = read_all ic in
  ignore (Unix.close_process_in ic); out

let shell_quote s =
  "'" ^ String.concat "'\\''" (String.split_on_char '\'' s) ^ "'"

let sql_escape s = String.concat "''" (String.split_on_char '\'' s)

let bodyfile = if Array.length Sys.argv > 1 then Sys.argv.(1) else ""

let jq filter =
  if bodyfile = "" then ""
  else String.trim (run_read (Printf.sprintf "jq -r %s %s 2>/dev/null"
                                (shell_quote filter) (shell_quote bodyfile)))

let db sql =
  run_read (Printf.sprintf "sqlite3 %s %s 2>/dev/null" (shell_quote db_path) (shell_quote sql))

let db_lines sql =
  List.filter (fun s -> s <> "") (String.split_on_char '\n' (String.trim (db sql)))

let db_scalar sql = match db_lines sql with x :: _ -> x | [] -> ""

let int_of s d = match int_of_string_opt (String.trim s) with Some n -> n | None -> d

(* ---- IP / CIDR math (pure OCaml) ---- *)
let ip_to_int s =
  match String.split_on_char '.' s with
  | [a; b; c; d] ->
    (match int_of_string_opt a, int_of_string_opt b, int_of_string_opt c, int_of_string_opt d with
     | Some a, Some b, Some c, Some d
       when List.for_all (fun x -> x >= 0 && x <= 255) [a; b; c; d] ->
       Some ((a lsl 24) lor (b lsl 16) lor (c lsl 8) lor d)
     | _ -> None)
  | _ -> None

let int_to_ip n =
  Printf.sprintf "%d.%d.%d.%d" ((n lsr 24) land 255) ((n lsr 16) land 255)
    ((n lsr 8) land 255) (n land 255)

let parse_cidr s =
  match String.split_on_char '/' s with
  | [ip; pfx] ->
    (match ip_to_int ip, int_of_string_opt pfx with
     | Some base, Some p when p >= 0 && p <= 32 ->
       let mask = if p = 0 then 0 else (0xFFFFFFFF lsl (32 - p)) land 0xFFFFFFFF in
       let network = base land mask in
       let broadcast = network lor ((lnot mask) land 0xFFFFFFFF) in
       Some (network, broadcast, p)
     | _ -> None)
  | _ -> None

(* ---- request / response ---- *)
let now_ms () =
  let wall = int_of_float (Unix.gettimeofday () *. 1000.) in
  let v = jq ".now_ms // empty" in
  if v = "" then wall else int_of v wall

(* One JSON object on stdout, with the status code injected as a "code" field. *)
let respond code json =
  let inner = String.sub json 1 (String.length json - 1) in
  if String.trim inner = "}" then Printf.printf "{\"code\":%d}" code
  else Printf.printf "{\"code\":%d,%s" code inner
let err code msg = respond code (Printf.sprintf "{\"error\":\"%s\"}" msg)

let audit ev pool_id ip client_id ts =
  ignore (db (Printf.sprintf
    "INSERT INTO audit(ts_ms,event,pool_id,ip,client_id) VALUES(%d,'%s',%s,%s,'%s');"
    ts (sql_escape ev)
    (match pool_id with Some p -> string_of_int p | None -> "NULL")
    (match ip with Some i -> string_of_int i | None -> "NULL")
    (sql_escape client_id)))

(* Is [ip] assignable to [client] right now? Usable range, not declined, not
   reserved to a different client, and not covered by a still-valid lease held by
   another client. Expired leases (expires <= now) do not block: the address is
   reclaimed. *)
let assignable_to pool_id network broadcast ip client now =
  ip > network && ip < broadcast
  && db_scalar (Printf.sprintf "SELECT 1 FROM declines WHERE pool_id=%d AND ip=%d;" pool_id ip) = ""
  && (let r = db_scalar (Printf.sprintf
        "SELECT client_id||'#' FROM reservations WHERE pool_id=%d AND ip=%d LIMIT 1;" pool_id ip) in
      (* "" = no reservation (assignable); "#" = pure exclusion (never); "X#" = held for X *)
      if r = "" then true else r = client ^ "#")
  && (let l = db_scalar (Printf.sprintf
        "SELECT client_id||'|'||expires_ms FROM leases WHERE pool_id=%d AND ip=%d AND state='active';"
        pool_id ip) in
      match String.split_on_char '|' l with
      | [c; e] -> c = client || int_of e 0 <= now
      | _ -> true)

let issue_lease pool_id ip client lease_secs now =
  let expires = now + (lease_secs * 1000) in
  ignore (db (Printf.sprintf
    "INSERT INTO leases(ip,pool_id,client_id,expires_ms,created_ms,state) \
     VALUES(%d,%d,'%s',%d,%d,'active') \
     ON CONFLICT(ip) DO UPDATE SET pool_id=%d,client_id='%s',expires_ms=%d,created_ms=%d,state='active';"
    ip pool_id (sql_escape client) expires now pool_id (sql_escape client) expires now));
  audit "lease" (Some pool_id) (Some ip) client now;
  expires

(* ---- handlers ---- *)
let h_create_pool () =
  let cidr = jq ".cidr // empty" in
  let lease_secs = jq ".lease_secs // empty" in
  match parse_cidr cidr with
  | None -> err 400 "invalid cidr"
  | Some (network, broadcast, prefix) ->
    if lease_secs = "" || int_of lease_secs 0 <= 0 then err 400 "invalid lease_secs"
    else begin
      let now = now_ms () in
      (* INSERT and last_insert_rowid() must share one sqlite3 process. *)
      let pid = int_of (db_scalar (Printf.sprintf
        "INSERT INTO pools(cidr,lease_secs,network,broadcast,prefix,created_ms) \
         VALUES('%s',%d,%d,%d,%d,%d); SELECT last_insert_rowid();"
        (sql_escape cidr) (int_of lease_secs 0) network broadcast prefix now)) 0 in
      let n = int_of (jq "(.reserved // []) | length") 0 in
      for i = 0 to n - 1 do
        let typ = jq (Printf.sprintf ".reserved[%d] | type" i) in
        if typ = "string" then begin
          match ip_to_int (jq (Printf.sprintf ".reserved[%d]" i)) with
          | Some ip ->
            ignore (db (Printf.sprintf
              "INSERT INTO reservations(pool_id,ip,client_id) VALUES(%d,%d,'');" pid ip))
          | None -> ()
        end else begin
          let ips = jq (Printf.sprintf ".reserved[%d].ip" i) in
          let cid = jq (Printf.sprintf ".reserved[%d].client_id // \"\"" i) in
          match ip_to_int ips with
          | Some ip ->
            ignore (db (Printf.sprintf
              "INSERT INTO reservations(pool_id,ip,client_id) VALUES(%d,%d,'%s');"
              pid ip (sql_escape cid)))
          | None -> ()
        end
      done;
      respond 201 (Printf.sprintf "{\"pool_id\":%d}" pid)
    end

let pool_row pid =
  let r = db_scalar (Printf.sprintf
    "SELECT network||' '||broadcast||' '||lease_secs FROM pools WHERE id=%d;" pid) in
  match String.split_on_char ' ' r with
  | [nw; bc; ls] -> Some (int_of nw 0, int_of bc 0, int_of ls 0)
  | _ -> None

let h_lease pid =
  match pool_row pid with
  | None -> err 404 "pool not found"
  | Some (network, broadcast, lease_secs) ->
    let client = jq ".client_id // empty" in
    if client = "" then err 400 "client_id required"
    else begin
      let now = now_ms () in
      let issue ip = respond 200 (Printf.sprintf "{\"ip\":\"%s\",\"expires_ms\":%d}"
                                    (int_to_ip ip) (issue_lease pid ip client lease_secs now)) in
      let assignable ip = assignable_to pid network broadcast ip client now in
      let held_by_other ip =
        let l = db_scalar (Printf.sprintf
          "SELECT client_id||'|'||expires_ms FROM leases WHERE pool_id=%d AND ip=%d AND state='active';"
          pid ip) in
        match String.split_on_char '|' l with
        | [c; e] -> c <> client && int_of e 0 > now
        | _ -> false in
      let reserved_ip =
        let r = db_scalar (Printf.sprintf
          "SELECT ip FROM reservations WHERE pool_id=%d AND client_id='%s' LIMIT 1;"
          pid (sql_escape client)) in
        if r = "" then None else Some (int_of r 0) in
      let requested_int =
        match (let s = jq ".requested_ip // empty" in if s = "" then None else ip_to_int s) with
        | Some ip when ip > network && ip < broadcast -> Some ip
        | _ -> None in
      let sticky =
        let r = db_scalar (Printf.sprintf
          "SELECT ip FROM leases WHERE pool_id=%d AND client_id='%s' ORDER BY created_ms DESC LIMIT 1;"
          pid (sql_escape client)) in
        if r = "" then None else Some (int_of r 0) in
      match requested_int with
      | Some ip when held_by_other ip -> err 409 "conflict"
      | _ ->
        (* preference order: static reservation, explicit request, sticky prior lease;
           then the lowest free usable address. Reclaims expired leases automatically. *)
        let prefs = List.filter_map (fun x -> x) [reserved_ip; requested_int; sticky] in
        let rec pick = function
          | ip :: rest -> if assignable ip then Some ip else pick rest
          | [] ->
            let rec scan ip =
              if ip >= broadcast then None
              else if assignable ip then Some ip else scan (ip + 1)
            in scan (network + 1) in
        (match pick prefs with
         | Some ip -> issue ip
         | None -> err 409 "pool_exhausted")
    end

let h_renew ip_str =
  match ip_to_int ip_str with
  | None -> err 400 "invalid ip"
  | Some ip ->
    let client = jq ".client_id // empty" in
    let row = db_scalar (Printf.sprintf
      "SELECT pool_id||' '||client_id FROM leases WHERE ip=%d AND state='active';" ip) in
    (match String.split_on_char ' ' row with
     | [pid; owner] when owner = client && client <> "" ->
       let pid = int_of pid 0 in
       (match pool_row pid with
        | Some (_, _, lease_secs) ->
          let now = now_ms () in
          let expires = now + lease_secs * 1000 in
          ignore (db (Printf.sprintf "UPDATE leases SET expires_ms=%d WHERE ip=%d;" expires ip));
          audit "renew" (Some pid) (Some ip) client now;
          respond 200 (Printf.sprintf "{\"expires_ms\":%d}" expires)
        | None -> err 404 "lease not found")
     | _ -> err 404 "lease not found")

let h_release ip_str =
  match ip_to_int ip_str with
  | None -> err 400 "invalid ip"
  | Some ip ->
    let owner = db_scalar (Printf.sprintf
      "SELECT client_id FROM leases WHERE ip=%d AND state='active';" ip) in
    if owner = "" then err 404 "lease not found"
    else begin
      ignore (db (Printf.sprintf "UPDATE leases SET state='released' WHERE ip=%d;" ip));
      audit "release" None (Some ip) owner (now_ms ());
      respond 200 "{\"released\":true}"
    end

let h_decline ip_str =
  match ip_to_int ip_str with
  | None -> err 400 "invalid ip"
  | Some ip ->
    let pid = int_of (db_scalar (Printf.sprintf
      "SELECT id FROM pools WHERE %d>network AND %d<broadcast ORDER BY id LIMIT 1;" ip ip)) 0 in
    ignore (db (Printf.sprintf
      "INSERT OR IGNORE INTO declines(ip,pool_id) VALUES(%d,%d);" ip pid));
    ignore (db (Printf.sprintf "UPDATE leases SET state='released' WHERE ip=%d;" ip));
    audit "decline" (Some pid) (Some ip) (jq ".client_id // \"\"") (now_ms ());
    respond 200 "{\"declined\":true}"

let h_status pid =
  match pool_row pid with
  | None -> err 404 "pool not found"
  | Some (network, broadcast, _) ->
    let now = now_ms () in
    let total = max 0 (broadcast - network - 1) in
    let excluded = int_of (db_scalar (Printf.sprintf
      "SELECT COUNT(*) FROM reservations WHERE pool_id=%d AND client_id='';" pid)) 0 in
    let declined = int_of (db_scalar (Printf.sprintf
      "SELECT COUNT(*) FROM declines WHERE pool_id=%d;" pid)) 0 in
    let active = int_of (db_scalar (Printf.sprintf
      "SELECT COUNT(*) FROM leases WHERE pool_id=%d AND state='active' AND expires_ms>%d;" pid now)) 0 in
    let leases =
      db_lines (Printf.sprintf
        "SELECT ip||','||client_id||','||expires_ms FROM leases \
         WHERE pool_id=%d AND state='active' AND expires_ms>%d ORDER BY ip;" pid now)
      |> List.map (fun r -> match String.split_on_char ',' r with
          | ip :: cid :: exp :: _ ->
            Printf.sprintf "{\"ip\":\"%s\",\"client_id\":\"%s\",\"expires_ms\":%s}"
              (int_to_ip (int_of ip 0)) cid exp
          | _ -> "")
      |> List.filter (fun s -> s <> "") in
    respond 200 (Printf.sprintf
      "{\"pool_id\":%d,\"total\":%d,\"active\":%d,\"available\":%d,\"excluded\":%d,\"declined\":%d,\"leases\":[%s]}"
      pid total active (max 0 (total - active - excluded - declined)) excluded declined
      (String.concat "," leases))

let () =
  match jq ".op" with
  | "healthz" -> respond 200 "{\"status\":\"ok\"}"
  | "create_pool" -> h_create_pool ()
  | "lease" -> h_lease (int_of (jq ".pool_id") 0)
  | "status" -> h_status (int_of (jq ".pool_id") 0)
  | "renew" -> h_renew (jq ".ip")
  | "release" -> h_release (jq ".ip")
  | "decline" -> h_decline (jq ".ip")
  | _ -> err 404 "unknown op"
