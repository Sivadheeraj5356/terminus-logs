use crate::hex::in_bounds;
use crate::model::{Map, Unit};

pub fn occupied(units: &[Unit], hex: [i32; 2], except: Option<&str>) -> bool {
    units.iter().any(|u| {
        u.alive
            && u.hex == hex
            && except.map(|id| id != u.id).unwrap_or(true)
    })
}

pub fn can_stand(map: &Map, units: &[Unit], hex: [i32; 2], except: Option<&str>) -> bool {
    if !in_bounds(map.width, map.height, hex[0], hex[1]) {
        return false;
    }
    if map.blocked[hex[1] as usize][hex[0] as usize] {
        return false;
    }
    !occupied(units, hex, except)
}

pub fn living_mut<'a>(units: &'a mut [Unit], id: &str) -> Option<&'a mut Unit> {
    units.iter_mut().find(|u| u.id == id && u.alive)
}

pub fn living_ref<'a>(units: &'a [Unit], id: &str) -> Option<&'a Unit> {
    units.iter().find(|u| u.id == id && u.alive)
}
