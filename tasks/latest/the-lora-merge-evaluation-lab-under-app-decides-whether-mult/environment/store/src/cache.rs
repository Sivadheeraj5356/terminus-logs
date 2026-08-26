use crate::stamp::seal_q;
use manifest::{BookE, FrameD, InputsB, ScopeC, Snapshot, StateA};
use std::{fs, path::Path};

fn encode(x: &Snapshot) -> String {
    format!(
        "{}|{}|{}|{}|{}|{}\n",
        x.token,
        x.request_id,
        x.state.score,
        x.state.ready,
        x.state.keys.join(","),
        x.state.labels.join(",")
    )
}

fn decode(text: &str) -> Option<Snapshot> {
    let p: Vec<_> = text.trim().split('|').collect();
    if p.len() != 6 {
        return None;
    }
    Some(Snapshot {
        token: p[0].into(),
        request_id: p[1].into(),
        state: StateA {
            score: p[2].parse().ok()?,
            ready: p[3].parse().ok()?,
            keys: p[4].split(',').filter(|x| !x.is_empty()).map(str::to_string).collect(),
            labels: p[5].split(',').filter(|x| !x.is_empty()).map(str::to_string).collect(),
        },
    })
}

pub fn commit(
    a: &StateA,
    b: &InputsB,
    c: &ScopeC,
    root: &str,
    use_latest: bool,
) -> Result<FrameD, String> {
    fs::create_dir_all(root).map_err(|e| e.to_string())?;
    let path = Path::new(root).join("current.dat");
    let prior = fs::read_to_string(&path).ok().and_then(|s| decode(&s));
    let mark = seal_q(a, b, c);
    let current = if let Some(old) = prior.as_ref().filter(|x| x.token == mark.value) {
        old.clone()
    } else {
        Snapshot {
            token: mark.value,
            state: a.clone(),
            request_id: b.request_id.clone(),
        }
    };
    let book = BookE {
        latest: use_latest.then(|| prior.clone()).flatten(),
        parts: c.parts.clone(),
    };
    let frame = replay::route_n(&current, &book).map_err(|e| e.to_string())?;
    fs::write(path, encode(&current)).map_err(|e| e.to_string())?;
    Ok(frame)
}
