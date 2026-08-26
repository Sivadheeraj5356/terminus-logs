use std::path::Path;

use hx01::model::{
    BackendRule, BackendState, Packet, PacketResult, PacketVerdict, RuleAction,
};
use hx01::Result;

use crate::protocol::{load_backend, save_backend};

pub struct BackendStore {
    pub path: std::path::PathBuf,
    pub state: BackendState,
}

impl BackendStore {
    pub fn open(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref().to_path_buf();
        let state = load_backend(&path)?;
        Ok(Self { path, state })
    }

    pub fn save(&self) -> Result<()> {
        save_backend(&self.path, &self.state)
    }

    pub fn simulate(&self, packet: &Packet) -> PacketResult {
        let mut matched = None;
        let mut verdict = PacketVerdict::Drop;
        for chain in self.state.chains.values() {
            for handle in chain {
                if let Some(rule) = self.state.rules.get(handle) {
                    if rule_matches(rule, packet) {
                        matched = rule.annotation.as_ref().map(|a| a.logical_id.clone());
                        verdict = match rule.action {
                            RuleAction::Allow => PacketVerdict::Allow,
                            RuleAction::Drop => PacketVerdict::Drop,
                            RuleAction::Log => PacketVerdict::Log,
                        };
                        break;
                    }
                }
            }
        }
        PacketResult {
            verdict,
            matched_rule: matched,
        }
    }

    pub fn bump_counter(&mut self, handle: u64, count: u64) {
        if let Some(rule) = self.state.rules.get_mut(&handle) {
            rule.counter += count;
        }
    }
}

fn rule_matches(rule: &BackendRule, packet: &Packet) -> bool {
    if let Some(port) = rule.dst_port {
        if port != packet.dst_port {
            return false;
        }
    }
    if let Some(src_set) = &rule.src_set {
        if let Some(members) = rule.state_sets_lookup_placeholder(src_set) {
            if !members.iter().any(|m| m == &packet.src) {
                return false;
            }
        }
    }
    if let Some(dst_set) = &rule.dst_set {
        if let Some(members) = rule.state_sets_lookup_placeholder(dst_set) {
            if !members.iter().any(|m| m == &packet.dst) {
                return false;
            }
        }
    }
    true
}

trait SetLookup {
    fn state_sets_lookup_placeholder(&self, set: &str) -> Option<&Vec<String>>;
}

impl SetLookup for BackendRule {
    fn state_sets_lookup_placeholder(&self, _set: &str) -> Option<&Vec<String>> {
        None
    }
}

pub fn simulate_with_sets(state: &BackendState, packet: &Packet) -> PacketResult {
    let store = BackendStore {
        path: Path::new("/dev/null").to_path_buf(),
        state: state.clone(),
    };
    let mut verdict = PacketVerdict::Drop;
    let mut matched = None;
    for chain in state.chains.values() {
        for handle in chain {
            if let Some(rule) = state.rules.get(handle) {
                if packet_matches_rule(state, rule, packet) {
                    matched = rule.annotation.as_ref().map(|a| a.logical_id.clone());
                    verdict = match rule.action {
                        RuleAction::Allow => PacketVerdict::Allow,
                        RuleAction::Drop => PacketVerdict::Drop,
                        RuleAction::Log => PacketVerdict::Log,
                    };
                    return PacketResult {
                        verdict,
                        matched_rule: matched,
                    };
                }
            }
        }
    }
    PacketResult {
        verdict,
        matched_rule: matched,
    }
}

fn packet_matches_rule(state: &BackendState, rule: &BackendRule, packet: &Packet) -> bool {
    if let Some(port) = rule.dst_port {
        if port != packet.dst_port {
            return false;
        }
    }
    if let Some(src_set) = &rule.src_set {
        if let Some(members) = state.sets.get(src_set) {
            if !members.iter().any(|m| m == &packet.src) {
                return false;
            }
        }
    }
    if let Some(dst_set) = &rule.dst_set {
        if let Some(members) = state.sets.get(dst_set) {
            if !members.iter().any(|m| m == &packet.dst) {
                return false;
            }
        }
    }
    true
}
