# HLS AES-128 segment contract

Inputs: /app/state/media-fetch.json and the media file it names.
Outputs under /app/state/hls/:

- index.m3u8 — VOD playlist
- segment000.ts, … — media segments
- key.bin — 16-byte AES key material (never copied into the encryption manifest)
- keyinfo.txt — FFmpeg keyinfo used during segmentation

Playlist EXT-X-KEY line must use METHOD=AES-128 and URI="urn:reelseal:key:<key_id>" where key_id is issued later by policy-bind. During segment, a provisional key_id placeholder rs-pending is allowed in the playlist URI; seal-manifest rewrites the playlist URI to the issued key_id and refreshes playlist_digest.

IV must be 32 lowercase hex characters (16 bytes). METHOD=NONE is forbidden.
