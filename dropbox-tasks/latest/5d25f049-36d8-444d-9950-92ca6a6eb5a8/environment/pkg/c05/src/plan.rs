use hx01::model::{BackendState, CompiledIntent, OwnershipManifest};

pub struct ReconcilePlan {
    pub adopt_pending: bool,
    pub rebuild_incomplete: bool,
    pub preserve_foreign: bool,
}

pub fn build_plan(
    _compiled: &CompiledIntent,
    _manifest: &OwnershipManifest,
    _backend: &BackendState,
) -> ReconcilePlan {
    ReconcilePlan {
        adopt_pending: true,
        rebuild_incomplete: true,
        preserve_foreign: true,
    }
}
