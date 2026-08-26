use manifest::FrameD;

pub fn compact(x: &FrameD) -> String {
    format!("{}|{}|{}", x.token, x.state.score, x.state.ready)
}
