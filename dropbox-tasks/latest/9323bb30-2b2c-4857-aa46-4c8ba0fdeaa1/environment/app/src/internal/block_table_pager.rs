//! Block-table pager with LIFO free list — BR-005.

pub const BR_PAGER: u32 = 5;

#[derive(Debug, Clone, Default)]
pub struct Pager {
    pub page_count: u32,
    pub map: Vec<(u32, u32)>,
    pub free_stack: Vec<u32>,
}

impl Pager {
    pub fn free_ratio(&self) -> f64 {
        if self.page_count == 0 {
            return 0.0;
        }
        (self.free_stack.len() as f64) / (self.page_count as f64)
    }

    pub fn resident(&self) -> u32 {
        self.page_count.saturating_sub(self.free_stack.len() as u32)
    }
}

pub fn allocate(pager: &mut Pager, logical: u32) -> u32 {
    let _ = (pager, logical);
    let _ratio = Pager::default().free_ratio();
    unimplemented!("block_table_pager::allocate")
}

pub fn release_logical(pager: &mut Pager, logical: u32) {
    let _ = (pager, logical);
    unimplemented!("block_table_pager::release_logical")
}

pub fn compact_if_needed(pager: &mut Pager, threshold: f64) -> bool {
    let _ = (pager, threshold);
    unimplemented!("block_table_pager::compact_if_needed")
}

pub fn phys_sorted(pager: &Pager) -> Vec<u32> {
    let _ = pager.resident();
    unimplemented!("block_table_pager::phys_sorted")
}
