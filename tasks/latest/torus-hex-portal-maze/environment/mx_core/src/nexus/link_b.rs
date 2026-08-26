use crate::sim::step::PortalLink;

/// Resolves portal destination from current cell.
pub fn link_b(pos: (i32, i32), links: &[PortalLink], _step_dir: u8) -> Option<(i32, i32)> {
    for link in links {
        let from = (link.from[0], link.from[1]);
        let to = (link.to[0], link.to[1]);
        if pos == from {
            return Some(to);
        }
        if pos == to {
            return Some(from);
        }
    }
    None
}
