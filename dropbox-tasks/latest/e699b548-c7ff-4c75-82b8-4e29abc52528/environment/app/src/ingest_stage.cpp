#include "ingest_stage.h"
#include "ingest_chain.h"
#include "staging_io.h"

IngestResult run_ingest_stage(
    const std::string& catalog_path,
    const Policy& policy,
    const std::vector<Fragment>& fragments) {
    IngestResult result;
    if (fragments.empty()) {
        result.error = "CATALOG_ERROR";
        return result;
    }
    auto chain = trace_ingest_chain(fragments, policy);
    StagingSnapshot snap;
    snap.version = 1;
    snap.catalog_path = catalog_path;
    snap.open_fragment_id = chain.open_fragment_id;
    snap.chain_fragment_ids = chain.chain_fragment_ids;
    snap.chain_overlaps = chain.chain_overlaps;
    snap.replica_summary = evaluate_replica_coverage(fragments, policy);
    snap.catalog_digest = catalog_digest_hex(fragments);
    result.snapshot = snap;
    result.ok = true;
    return result;
}
