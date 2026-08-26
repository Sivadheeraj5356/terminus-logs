# Corpus stamp

`corpus_stamp` is SHA-256 of the concatenation of each required manifest's compact JSON (`sort_keys=True`, separators compact) in this filename order:

1. `conversation_sessions.json`
2. `prompt_turn_log.json`
3. `retrieval_injections.json`
4. `tool_execution_outputs.json`
5. `system_instruction_versions.json`
6. `model_output_failures.json`
7. `contamination_policy.json`
8. `session_order_timeline.json`

Object key order is normalized; array element order still affects the digest.
