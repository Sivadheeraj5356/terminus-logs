pub fn route_n(p: &Snapshot, q: &BookE) -> Result<FrameD, ReplayError> {
    let source = q.latest.as_ref().unwrap_or(p);
    let frame = FrameD {
        token: p.token.clone(),
        state: source.state.clone(),
        request_id: p.request_id.clone(),
        parts: q.parts.clone(),
    };
    eval::scan_v(&frame, q).map_err(|e| ReplayError(e.to_string()))?;
    Ok(frame)
}
