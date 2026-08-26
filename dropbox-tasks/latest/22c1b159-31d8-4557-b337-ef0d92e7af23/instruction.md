Implement a single-pass, bounded-memory online classifier in Java. The stream contains one-minute household power rows with missing measurement gaps and delayed sub-meter labels. For each prediction request, your program must emit the probability that the source row's withheld sub-meter share crosses the request threshold, using only state available before any labels released at that same event.

Your implementation lives in /app/environment/src/Solver.java and must build offline with javac. The file currently present there is only a placeholder stub that emits an empty result; replace it with a complete implementation. The verifier compiles it and runs java -cp /app/environment/src Solver <data-dir> once per stream. The program must print exactly one JSON document to standard output.

Each data directory contains readings.csv, prediction_requests.csv, label_arrivals.csv, learner_config.csv, and score_windows.csv. Parse CSV columns by header name, not by position. Hidden streams use different chronological windows, missing-run patterns, same-event labels, terminal labels, duplicate requests, and column orders.

Process reading events in increasing event_id. Missing rows apply gap decay and create no predictions. For observed rows, emit all prediction requests before applying labels that arrive at the same event. Labels released after the final reading are still processed as a terminal flush for scoring and model updates.

The output JSON must contain n_events, n_predictions, n_labels, n_missing_events, predictions, resets, windows, and final_state. Prediction rows are {request_id,event_id,probability}; reset rows are {event_id,daypart_id}; window rows are {window_id,n_scored,brier,log_loss}; final_state contains gap_events, labels_applied, and the ordered daypart states. Floating point values must be accurate within 1e-9.

The complete algorithmic contract, including gap decay, daypart EWMA updates, Page-Hinkley reset cooldown, log-loss clamping, score-window membership, memory bound, and the full JSON schema, is specified in /app/environment/docs/contract.md.
