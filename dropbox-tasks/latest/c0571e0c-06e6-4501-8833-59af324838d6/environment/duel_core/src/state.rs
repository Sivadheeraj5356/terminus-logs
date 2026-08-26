pub const POS_MIN: i32 = 0;
pub const POS_MAX: i32 = 9;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Fighter {
    pub pos: u8,
    pub hp: u8,
    pub meter: u8,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct GameState {
    pub p0: Fighter,
    pub p1: Fighter,
}

impl GameState {
    pub fn initial() -> GameState {
        GameState {
            p0: Fighter { pos: 2, hp: 100, meter: 0 },
            p1: Fighter { pos: 7, hp: 100, meter: 0 },
        }
    }
}
