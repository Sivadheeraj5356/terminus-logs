use indexmap::IndexMap;
use serde::{Deserialize, Serialize};

use crate::ids::LogicalId;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum RuleAction {
    Allow,
    Drop,
    Log,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AddressSet {
    pub id: LogicalId,
    pub tenant: String,
    pub members: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RuleSpec {
    pub id: LogicalId,
    pub tenant: String,
    pub action: RuleAction,
    pub src_set: Option<LogicalId>,
    pub dst_set: Option<LogicalId>,
    pub dst_port: Option<u16>,
    pub ordered_index: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ChainSpec {
    pub id: LogicalId,
    pub tenant: String,
    pub rules: Vec<LogicalId>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PolicyIntent {
    pub tenants: IndexMap<String, TenantIntent>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TenantIntent {
    pub sets: IndexMap<String, AddressSet>,
    pub chains: IndexMap<String, ChainSpec>,
    pub rules: IndexMap<String, RuleSpec>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CompiledObject {
    pub visible_name: String,
    pub logical_id: LogicalId,
    pub kind: crate::ids::ObjectKind,
    pub semantic_revision: String,
    pub payload: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CompiledIntent {
    pub objects: Vec<CompiledObject>,
    pub canonical_digest: String,
    pub input_chain_order: Vec<LogicalId>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Packet {
    pub src: String,
    pub dst: String,
    pub dst_port: u16,
    pub proto: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PacketVerdict {
    Allow,
    Drop,
    Log,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PacketResult {
    pub verdict: PacketVerdict,
    pub matched_rule: Option<LogicalId>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Annotation {
    pub managed: bool,
    pub logical_id: LogicalId,
    pub generation: u64,
    pub phase: String,
    pub tenant: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub counter_lineage: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BackendRule {
    pub handle: u64,
    pub visible_name: String,
    pub annotation: Option<Annotation>,
    pub action: RuleAction,
    pub src_set: Option<String>,
    pub dst_set: Option<String>,
    pub dst_port: Option<u16>,
    pub chain: String,
    pub counter: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Default)]
pub struct BackendState {
    pub sets: IndexMap<String, Vec<String>>,
    pub chains: IndexMap<String, Vec<u64>>,
    pub rules: IndexMap<u64, BackendRule>,
    pub next_handle: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ManifestEntry {
    pub logical_id: LogicalId,
    pub visible_name: String,
    pub kind: crate::ids::ObjectKind,
    pub generation: u64,
    pub semantic_revision: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub counter_lineage: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ManifestGeneration {
    pub generation: u64,
    pub phase: String,
    pub entries: Vec<ManifestEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct OwnershipManifest {
    pub schema_version: u32,
    pub committed: ManifestGeneration,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pending: Option<ManifestGeneration>,
}

impl Default for OwnershipManifest {
    fn default() -> Self {
        Self {
            schema_version: 2,
            committed: ManifestGeneration::default(),
            pending: None,
        }
    }
}

impl Default for ManifestGeneration {
    fn default() -> Self {
        Self {
            generation: 0,
            phase: "empty".into(),
            entries: Vec::new(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RuntimeOverride {
    pub action: Option<RuleAction>,
    pub tenant: Option<String>,
    pub ownership_scope: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Default)]
pub struct RuntimeOverrides {
    #[serde(default)]
    pub rules: IndexMap<String, RuntimeOverride>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DropInMeta {
    pub path: String,
    pub priority: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EffectiveConfig {
    pub tenants: IndexMap<String, TenantIntent>,
    pub sources: Vec<DropInMeta>,
}
