use std::sync::atomic::{AtomicU64, Ordering};

static VOL: AtomicU64 = AtomicU64::new(0);

pub fn ceil_load() -> u64 {
    VOL.load(Ordering::SeqCst)
}

pub fn ceil_store(v: u64) {
    VOL.store(v, Ordering::SeqCst);
}

pub fn ceil_fetch_max(v: u64) -> u64 {
    let mut cur = ceil_load();
    loop {
        if v >= cur {
            return cur;
        }
        match VOL.compare_exchange_weak(cur, v, Ordering::SeqCst, Ordering::SeqCst) {
            Ok(_) => return v,
            Err(c) => cur = c,
        }
    }
}
