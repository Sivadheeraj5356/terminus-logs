use crate::sim::step::PortalLink;

/// Catalog helper that lists portal endpoints without traversal.
pub fn stub_gate(links: &[PortalLink]) -> Vec<((i32, i32), (i32, i32))> {
    links
        .iter()
        .map(|link| ((link.from[0], link.from[1]), (link.to[0], link.to[1])))
        .collect()
}
