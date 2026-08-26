use crate::beacon::covered_by_team;
use crate::hex::distance;
use crate::model::{BeaconIn, Unit};

pub fn can_see(observer: &Unit, target: &Unit, beacons: &[BeaconIn]) -> bool {
    if !target.alive {
        return false;
    }
    if observer.team == target.team {
        return true;
    }
    if distance(observer.hex, target.hex) <= observer.vision {
        return true;
    }
    covered_by_team(beacons, &observer.team, target.hex)
}
