use super::fold::GaugeView;
use crate::q_rd::AccBuf;

pub fn gauge_view(buf: &AccBuf, plan_ceiling: f64) -> GaugeView {
    let mut sum = 0.0f64;
    for value in &buf.acc {
        sum += (*value as f64) * (*value as f64);
    }
    let l2_norm = sum.sqrt();
    GaugeView {
        l2_norm,
        within_plan: l2_norm <= plan_ceiling,
    }
}

pub fn emit_gauge(buf: &AccBuf, plan_ceiling: f64) {
    let view = gauge_view(buf, plan_ceiling);
    println!(
        "gauge l2={:.4} within={}",
        view.l2_norm, view.within_plan
    );
}
