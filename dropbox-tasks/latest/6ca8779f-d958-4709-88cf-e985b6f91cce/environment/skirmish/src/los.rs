use crate::hex::{hex_line, in_bounds};
use crate::model::Map;

pub fn has_los(map: &Map, from: [i32; 2], to: [i32; 2]) -> bool {
    if !in_bounds(map.width, map.height, from[0], from[1])
        || !in_bounds(map.width, map.height, to[0], to[1])
    {
        return false;
    }
    let start_e = map.elevation[from[1] as usize][from[0] as usize];
    let end_e = map.elevation[to[1] as usize][to[0] as usize];
    let thresh = start_e.max(end_e) + 1;
    let line = hex_line(from, to);
    for (idx, cell) in line.iter().enumerate() {
        if idx == 0 || idx + 1 == line.len() {
            continue;
        }
        if !in_bounds(map.width, map.height, cell[0], cell[1]) {
            return false;
        }
        if map.blocked[cell[1] as usize][cell[0] as usize] {
            return false;
        }
        if map.elevation[cell[1] as usize][cell[0] as usize] >= thresh {
            return false;
        }
    }
    true
}
