use crate::types::validator::Validator;

pub fn identity(validator: &Validator) -> String {
    format!(
        "{}:{}:{}:{}",
        validator.id, validator.network_id, validator.owner_id, validator.stake
    )
}
