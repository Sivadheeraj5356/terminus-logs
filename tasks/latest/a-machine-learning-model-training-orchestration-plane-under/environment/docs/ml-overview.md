# Machine-learning training overview

This repository is a **machine-learning** offline training orchestration plane, not a generic application server.

## Learning objective

Run a supervised tabular training workflow that:

1. Ingests feature parquet-style batches
2. Normalizes feature schemas for training
3. Syncs features into a feature store
4. Fits a gradient-boosted model (`train`)
5. Scores holdout metrics (`evaluate`)
6. Publishes the trained model artifact
7. Runs a compliance audit node alongside the DAG

Training checkpoints, failed-run recovery, and deterministic replay exist so ML operators can resume interrupted experiment runs and re-derive identical lineage digests for model audit.

## Why recovery and certificates matter here

Model-training jobs are long-running and checkpointed. The recovery certificate binds plan, journal, replay, and verification digests so an ML platform can prove which training graph produced a published model artifact.
