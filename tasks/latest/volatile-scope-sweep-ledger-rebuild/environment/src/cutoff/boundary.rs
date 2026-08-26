pub fn journal_included(rotate_gen: u32, bound_rotate: u32, slack: u32) -> bool {
    rotate_gen < bound_rotate + slack
}
