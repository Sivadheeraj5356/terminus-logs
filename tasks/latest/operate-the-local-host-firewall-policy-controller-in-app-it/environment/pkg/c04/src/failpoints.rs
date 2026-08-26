use hx01::PolicyError;

pub fn check_failpoint(name: &str) -> Result<(), PolicyError> {
    if let Ok(fp) = std::env::var("NX_FAILPOINT") {
        if fp == name {
            return Err(PolicyError::Failpoint(name.to_string()));
        }
    }
    Ok(())
}

pub const AFTER_STAGE_SETS: &str = "after-stage-sets";
pub const AFTER_STAGE_CHAINS: &str = "after-stage-chains";
pub const AFTER_PUBLISH_REFERENCES: &str = "after-publish-references";
pub const AFTER_MANIFEST_PUBLISH: &str = "after-manifest-publish";
pub const DURING_CLEANUP: &str = "during-cleanup";
