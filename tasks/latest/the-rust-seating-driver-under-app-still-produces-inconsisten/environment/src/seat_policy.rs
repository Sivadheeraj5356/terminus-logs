pub enum SeatAction {
    Skip,
    Replace { old_checksum: u32 },
    Seat,
}

pub fn decide_seat_action(
    existing_checksum: Option<u32>,
    new_checksum: u32,
) -> SeatAction {
    match existing_checksum {
        None => SeatAction::Seat,
        Some(old) if old == new_checksum => SeatAction::Skip,
        Some(old) => SeatAction::Replace { old_checksum: old },
    }
}
