use hx01::model::BackendState;

pub struct BatchPlan {
    pub label: String,
}

pub fn stage_sets(state: &mut BackendState) -> BatchPlan {
    BatchPlan {
        label: "stage-sets".into(),
    }
}

pub fn stage_chains(state: &mut BackendState) -> BatchPlan {
    let _ = state;
    BatchPlan {
        label: "stage-chains".into(),
    }
}

pub fn publish_references(state: &mut BackendState) -> BatchPlan {
    let _ = state;
    BatchPlan {
        label: "publish-references".into(),
    }
}
