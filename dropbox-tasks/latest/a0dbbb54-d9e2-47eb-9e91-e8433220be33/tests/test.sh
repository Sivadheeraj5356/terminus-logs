#!/bin/bash

mkdir -p /logs/verifier
STATUS=0

rm -rf /tmp/bundles && mkdir -p /tmp/bundles/b0_public
for fx in terrain_cells cover_labels fold_registry fold_scores_calibration fold_scores_evaluation decision_grid; do
    cp /tests/fixtures/$fx.csv /tmp/bundles/b0_public/ || STATUS=1
done

PUB_DIR=/tmp/bundles/b0_public HIDDEN_ROOT=/tmp/bundles python3 /tests/generate_hidden_data.py; rc=$?; [ $rc -ne 0 ] && STATUS=1

rm -rf /tmp/out_0 /tmp/out_1 /tmp/out_2 /tmp/out_3 /tmp/out_4 /tmp/out_5 /tmp/out_6
mkdir -p /tmp/out_0 /tmp/out_1 /tmp/out_2 /tmp/out_3 /tmp/out_4 /tmp/out_5 /tmp/out_6

CONFORMAL_DATA_DIR=/tmp/bundles/b0_public CONFORMAL_OUT_DIR=/tmp/out_0 Rscript /app/environment/analysis.R; rc=$?; [ $rc -ne 0 ] && STATUS=1
BUNDLE_DIR=/tmp/bundles/b0_public OUT_DIR=/tmp/out_0 python3 -m pytest /tests/test_outputs.py -rA --tb=line --no-header -q --ctrf /logs/verifier/ctrf_0.json; rc=$?; [ $rc -ne 0 ] && STATUS=1

CONFORMAL_DATA_DIR=/tmp/bundles/h1_refold_k3 CONFORMAL_OUT_DIR=/tmp/out_1 Rscript /app/environment/analysis.R; rc=$?; [ $rc -ne 0 ] && STATUS=1
BUNDLE_DIR=/tmp/bundles/h1_refold_k3 OUT_DIR=/tmp/out_1 python3 -m pytest /tests/test_outputs.py -rA --tb=line --no-header -q --ctrf /logs/verifier/ctrf_1.json; rc=$?; [ $rc -ne 0 ] && STATUS=1

CONFORMAL_DATA_DIR=/tmp/bundles/h2_coarse_k2 CONFORMAL_OUT_DIR=/tmp/out_2 Rscript /app/environment/analysis.R; rc=$?; [ $rc -ne 0 ] && STATUS=1
BUNDLE_DIR=/tmp/bundles/h2_coarse_k2 OUT_DIR=/tmp/out_2 python3 -m pytest /tests/test_outputs.py -rA --tb=line --no-header -q --ctrf /logs/verifier/ctrf_2.json; rc=$?; [ $rc -ne 0 ] && STATUS=1

CONFORMAL_DATA_DIR=/tmp/bundles/h3_empty_fold CONFORMAL_OUT_DIR=/tmp/out_3 Rscript /app/environment/analysis.R; rc=$?; [ $rc -ne 0 ] && STATUS=1
BUNDLE_DIR=/tmp/bundles/h3_empty_fold OUT_DIR=/tmp/out_3 python3 -m pytest /tests/test_outputs.py -rA --tb=line --no-header -q --ctrf /logs/verifier/ctrf_3.json; rc=$?; [ $rc -ne 0 ] && STATUS=1

CONFORMAL_DATA_DIR=/tmp/bundles/h4_k1_degenerate CONFORMAL_OUT_DIR=/tmp/out_4 Rscript /app/environment/analysis.R; rc=$?; [ $rc -ne 0 ] && STATUS=1
BUNDLE_DIR=/tmp/bundles/h4_k1_degenerate OUT_DIR=/tmp/out_4 python3 -m pytest /tests/test_outputs.py -rA --tb=line --no-header -q --ctrf /logs/verifier/ctrf_4.json; rc=$?; [ $rc -ne 0 ] && STATUS=1

CONFORMAL_DATA_DIR=/tmp/bundles/h5_theta_edges CONFORMAL_OUT_DIR=/tmp/out_5 Rscript /app/environment/analysis.R; rc=$?; [ $rc -ne 0 ] && STATUS=1
BUNDLE_DIR=/tmp/bundles/h5_theta_edges OUT_DIR=/tmp/out_5 python3 -m pytest /tests/test_outputs.py -rA --tb=line --no-header -q --ctrf /logs/verifier/ctrf_5.json; rc=$?; [ $rc -ne 0 ] && STATUS=1

CONFORMAL_DATA_DIR=/tmp/bundles/h6_roworder CONFORMAL_OUT_DIR=/tmp/out_6 Rscript /app/environment/analysis.R; rc=$?; [ $rc -ne 0 ] && STATUS=1
BUNDLE_DIR=/tmp/bundles/h6_roworder OUT_DIR=/tmp/out_6 python3 -m pytest /tests/test_outputs.py -rA --tb=line --no-header -q --ctrf /logs/verifier/ctrf_6.json; rc=$?; [ $rc -ne 0 ] && STATUS=1

python3 /tests/merge_ctrf.py /logs/verifier/ctrf.json /logs/verifier/ctrf_0.json /logs/verifier/ctrf_1.json /logs/verifier/ctrf_2.json /logs/verifier/ctrf_3.json /logs/verifier/ctrf_4.json /logs/verifier/ctrf_5.json /logs/verifier/ctrf_6.json || STATUS=1

test "$STATUS" -eq 0
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
