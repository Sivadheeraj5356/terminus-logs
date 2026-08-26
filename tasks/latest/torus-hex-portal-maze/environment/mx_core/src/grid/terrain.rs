use std::collections::HashMap;

pub fn terrain_cost(q: i32, r: i32, table: &HashMap<String, u32>) -> u32 {
    let key = format!("{q},{r}");
    *table.get(&key).unwrap_or(&1)
}
