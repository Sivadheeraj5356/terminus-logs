use crate::NodeH;

#[derive(Clone, Debug)]
pub struct TeleFrame {
    pub depth: u32,
    pub label: String,
    pub score: i32,
}

pub struct ShadowBuf {
    frames: Vec<TeleFrame>,
    cap: usize,
}

impl ShadowBuf {
    pub fn new(cap: usize) -> Self {
        Self {
            frames: Vec::with_capacity(cap),
            cap,
        }
    }

    pub fn push_frame(&mut self, depth: u32, label: &str, score: i32) {
        if self.frames.len() >= self.cap {
            self.frames.remove(0);
        }
        self.frames.push(TeleFrame {
            depth,
            label: label.to_string(),
            score,
        });
    }

    pub fn render(&self) -> String {
        let mut out = String::new();
        for (i, f) in self.frames.iter().enumerate() {
            out.push_str(&format!(
                "{:03}|d{}|{}|{}\n",
                i, f.depth, f.label, f.score
            ));
        }
        out
    }
}

/// Logs expansion telemetry for dry-run mode without affecting certificate rows.
pub fn shadow_log(root: &NodeH, budget: u32) -> String {
    let mut buf = ShadowBuf::new(64);
    fn walk(n: &NodeH, depth: u32, budget: u32, buf: &mut ShadowBuf) {
        if depth >= budget {
            return;
        }
        buf.push_frame(depth, &format!("n{}", n.ix), n.score);
        for kid in &n.kids {
            walk(kid, depth + 1, budget, buf);
        }
    }
    walk(root, 0, budget, &mut buf);
    buf.render()
}
