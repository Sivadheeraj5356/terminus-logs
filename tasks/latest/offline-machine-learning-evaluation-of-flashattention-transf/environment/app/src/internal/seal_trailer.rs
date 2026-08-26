//! Combinatorial Blueprint: seal writes spine trailer (tip XOR spine_salt); next plan validates before LIFO reset.
//! Axiomatic Blindspot: plan that truncates without trailer check accepts stale spine state.
//! Silent Failure Point: wrong salt or tip leaves trailer valid for agents who skip XOR binding.

use anyhow::Result;

pub fn trailer_path() -> String {
    unimplemented!("seal_trailer::trailer_path")
}

pub fn mark(_tip: u64, _spine_salt: u64) -> u64 {
    unimplemented!("seal_trailer::mark")
}

pub fn encode_hex(_mark: u64) -> String {
    unimplemented!("seal_trailer::encode_hex")
}

pub fn decode_hex(_s: &str) -> Result<u64> {
    unimplemented!("seal_trailer::decode_hex")
}

pub fn persist(_mark: u64) -> Result<()> {
    unimplemented!("seal_trailer::persist")
}

pub fn clear() {
    unimplemented!("seal_trailer::clear")
}

pub fn load_optional() -> Result<Option<u64>> {
    unimplemented!("seal_trailer::load_optional")
}

pub fn require_valid(_tip: u64, _spine_salt: u64) -> Result<()> {
    unimplemented!("seal_trailer::require_valid")
}
