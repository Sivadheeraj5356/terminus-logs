use crate::parser::{self, Slot};

pub fn sort_slots(slots: &mut [Slot]) {
    slots.sort_by(|a, b| {
        parser::canonical_resource(&a.resource)
            .cmp(&parser::canonical_resource(&b.resource))
            .then(b.start_ms.cmp(&a.start_ms))
    });
}
