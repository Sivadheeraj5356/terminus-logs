# Route manifest contract

The escape pipeline must write `/app/output/route_manifest.json`.

## schema_tag

The `schema_tag` field must be set to the exact string `route_manifest_v1`.

## rooms

The `rooms` field must be an ordered list of room identifiers from the live topology `start` room through the `exit` room, inclusive. Each consecutive pair must be connected by a single legal edge in the topology document returned by the service.

## moves

The `moves` field must be an ordered list of move tokens, one per edge between consecutive rooms. Legal tokens are exactly `N`, `S`, `E`, and `W`. `moves.len()` must equal `rooms.len() - 1`. Move `moves[i]` must be the label on the edge from `rooms[i]` to `rooms[i + 1]` in the live topology.

## api_evidence

Object with:

- `listen_port` (integer): must report the TCP port where the live topology service is listening
- `graph_path` (string): must report the absolute path of the graph file the live service has open
- `endpoint` (string): HTTP path used to fetch topology; must be `/v1/topology`
- `status_code` (integer): HTTP status from that fetch; must be `200`

## Checksums

Each checksum field is computed as the first 16 lowercase hexadecimal characters of sha256 over UTF-8 bytes.

- `rooms_checksum` is computed as sha256 of the room identifiers joined with a single `|` character (no trailing separator)
- `moves_checksum` is computed as sha256 of the move tokens joined with no separator
- `evidence_checksum` is computed as sha256 of `listen_port`, `graph_path`, and `endpoint` joined with `|` in that order (decimal port text, no spaces)
- `manifest_checksum` is computed as sha256 of `rooms_checksum`, `moves_checksum`, and `evidence_checksum` joined with `|` in that order

Example for rooms `["A","B"]`: digest input is `A|B`.
Example for moves `["E","N"]`: digest input is `EN`.
Example for evidence port `1234`, path `/tmp/g.json`, endpoint `/v1/topology`: digest input is `1234|/tmp/g.json|/v1/topology`.
