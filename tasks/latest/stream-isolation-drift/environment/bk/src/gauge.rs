use super::Pool;

pub fn emit_gauge(pool: &Pool, ceiling: f64) {
    let l2: f64 = pool.tape.iter().map(|v| v * v).sum::<f64>().sqrt();
    let within = if l2 <= ceiling { "true" } else { "false" };
    println!("gauge l2={l2:.4} within={within}");
}
