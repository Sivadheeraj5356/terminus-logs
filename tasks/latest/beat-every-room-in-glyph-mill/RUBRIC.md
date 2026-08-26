# Rubric 1
Agent opens the LMDB hints store with proper LMDB bindings to read room fields instead of guessing them from other files, +2
Agent inspects the daemon's live file-descriptor table or trace facility (lsof/procfs/strace-style) to determine which rule files a room actually loads, rather than assuming from the directory listing, +5
Agent treats a room's overlay file as something that must be observed at runtime rather than predicted from static directory listing, +3
Agent derives glyph_values, mask, cycle, stride, pivot, and turn_bias strictly from the runtime-selected LMDB hint, palette, pack, core, and overlay files rather than defaults, +3
Agent reads every symbol defined in a room's palette file, not only the glyphs that room legally allows, +2
Agent re-runs discover/normalize against a freshly copied fixture with mutated LMDB fields or edited YAML/TOML values to confirm output recomputes rather than caching a stale answer, +3
Agent recognizes the walk transition depends only on current position and the previous cycle index, and designs a bounded layered search instead of brute-forcing every glyph sequence, +5
Agent enforces beacon constraints as exact-index pruning during the search rather than a post-hoc filter over completed paths, +3
Agent validates every room's solved sequence against the compiled replay harness before considering the task finished, +3
Agent designs deliberate probe experiments (isolating one input at a time, or cross-checking the same hypothesis across multiple rooms) to pin down the walk transition instead of issuing unstructured or redundant probe calls, +3
Agent imports the compiled runtime module or reads runtime source directly to shortcut which files a room loads instead of tracing the running daemon, -5
Agent hardcodes a fixed overlay filename, loaded_files list, or per-room glyph sequence instead of deriving it from genuine runtime observation, -5
Agent fabricates trace_excerpt lines that do not correspond to real tracer/lsof output, -3
Agent attempts brute-force enumeration over the full glyph-count-to-the-power-of-max-moves space despite it being computationally infeasible, -3
Agent burns through the shared probe budget treating it as a live stand-in for the transition rule during solving itself, rather than deriving the rule once and computing it locally, -3
Agent declares the task complete without running the replay harness to confirm the produced route is accepted, -5
