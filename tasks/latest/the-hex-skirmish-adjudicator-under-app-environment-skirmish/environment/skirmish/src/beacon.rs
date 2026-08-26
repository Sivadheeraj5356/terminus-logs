use crate::hex::distance;
use crate::model::BeaconIn;

pub fn covered_by_team(beacons: &[BeaconIn], team: &str, hex: [i32; 2]) -> bool {
    beacons
        .iter()
        .any(|b| distance(b.hex, hex) <= b.radius && !team.is_empty())
}
