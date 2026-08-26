/// cg_bear_v checks whether a mast calibration generation meets the service floor.
#[no_mangle]
pub extern "C" fn cg_bear_v(epoch: i64, floor: i64) -> i64 {
    if epoch > floor {
        return 1;
    }
    0
}
