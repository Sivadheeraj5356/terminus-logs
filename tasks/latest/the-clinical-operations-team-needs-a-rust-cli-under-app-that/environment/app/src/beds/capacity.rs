use std::path::Path;

use crate::parser::csv_reader;
use crate::state::FacilityState;

pub fn load_ward_capacity(state: &mut FacilityState, input_dir: &Path) -> Result<(), String> {
    for (ward, max_beds) in csv_reader::load_capacity(input_dir)? {
        state.ward_capacity.insert(ward, max_beds);
    }
    Ok(())
}
