# Physics scene input format

Load `scene_*.json` from `/app/scenarios/` unless `PHYSICS_SCENE_DIR` points elsewhere.
Only analyze `scene_01.json` through `scene_20.json` by `scene_id`; ignore other `scene_*.json`.

Replay walks `frames[]` in JSON array order; do not sort frames by the `frame` integer before analysis.

`impulse_chain_len` in the report is `0` when every frame has an empty `contacts` array; otherwise it is the longest same-frame chain length (minimum `1` when any contacts exist).

Each scene file:

```
{
  "scene_id": "scene_XX",
  "bodies": {
    "BODY_ID": { "layer": int, "mass": float, "sleeping": bool }
  },
  "layers": { "LAYER_ID": mask_int },
  "frames": [
    {
      "frame": int,
      "contacts": [
        {
          "contact_id": string,
          "body_a": string,
          "body_b": string,
          "normal_y": float,
          "penetration_m": float,
          "friction": float,
          "restitution": float,
          "manifold_id": string,
          "impulse_normal": float,
          "impulse_tangent": float
        }
      ],
      "positions": { "BODY_ID": [x, y] },
      "velocities": { "BODY_ID": [vx, vy] },
      "broadphase": [[body_a, body_b], ...],
      "narrowphase": [[body_a, body_b], ...],
      "constraints": [
        { "body_a": string, "body_b": string, "separation_m": float, "limit_m": float }
      ]
    }
  ],
  "stress": {
    "schedules": [
      { "schedule_id": string, "frame_order": [ int ] }
    ]
  }
}
```

Layer mask values are bitmasks. Layer id L may collide with layer id M only when
both `(mask[L] & (1 << (M-1)))` and `(mask[M] & (1 << (L-1)))` are non-zero.
When `layers.enforce_mask` is true, emit `layer_filter_miss` only if both bodies exist in `bodies`, both layer masks exist, and the masks do not intersect; otherwise skip the layer check.

Restitution check: clamp when `restitution` is outside policy min/max. Separating check (once per unordered body pair): when `restitution > 0` and `normal_y > 0.5`, compute `(velocities[body_a].y - velocities[body_b].y) * normal_y` using the contact's `body_a` and `body_b` keys (not alphabetical body names); if positive, emit `separating normal velocity with positive restitution`. When `normal_y` is not greater than 0.5, or the relative normal velocity is not positive (approaching), skip the separating check.

Sleep activation compares `hypot(velocities[id].x, velocities[id].y)` against `sleep.activation_velocity_threshold_m_s` for bodies marked `sleeping: true`.

Tunneling compares consecutive `frames[]` entries in file order using `tunneling.velocity_threshold_m_s` and `tunneling.timestep_ns` from policy.

`friction.cumulative_drift_threshold_m_s` is compared per contact per frame against `abs(impulse_tangent)` (the YAML key name is historical; do not sum tangent impulse across frames).

Broadphase pairs are unordered; `["body_b","body_a"]` matches `["body_a","body_b"]` for subset checks.

Stress `frame_order` lists frame indices to replay for validation. Indices not present in the scene are skipped during replay but still count toward `len(frame_order)` for stress span rules in OUTPUT_SCHEMA. Scenes with no stress schedules report `validated` true. Span overrides apply only when every schedule is a prefix (`len < F`) or every schedule spans all frames (`len >= F`); mixed schedules keep the pass-count result without override.

Optional top-level scene fields `format_version`, `reserved`, `capture_checksum`, and `payload_len` may appear in fixture files; ignore them when replaying contacts.
