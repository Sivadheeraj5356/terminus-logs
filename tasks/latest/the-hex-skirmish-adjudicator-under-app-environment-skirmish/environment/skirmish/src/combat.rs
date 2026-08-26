use crate::constants::BASE_STRIKE;
use crate::traits_mod::has_trait;

pub fn strike_damage(attacker_traits: &[String], target_armor: i32) -> i32 {
    if has_trait(attacker_traits, "PIERCE") {
        (BASE_STRIKE - target_armor).max(1)
    } else {
        (BASE_STRIKE - target_armor).max(1)
    }
}
