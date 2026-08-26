use crate::types::ReadingRow;

pub fn sort_rows(rows: &mut [ReadingRow]) {
    rows.sort_by(|a, b| {
        a.line_index
            .cmp(&b.line_index)
            .then_with(|| {
                a.temp_c
                    .partial_cmp(&b.temp_c)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
    });
}
