use std::cmp::Ordering;
use std::collections::HashMap;
use std::fs;
use std::path::Path;

const NEG_INF: i64 = i64::MIN / 4;

#[derive(Clone)]
struct Params {
    wave_count: usize,
    max_actions_per_wave: usize,
    max_total_review_minutes: i64,
    min_distinct_owners: usize,
    min_preserved_evidence_points: i64,
}

#[derive(Clone)]
struct Scenario {
    scenario_id: String,
    confidence_weight: i64,
}

#[derive(Clone)]
struct Approval {
    review_minutes: i64,
}

#[derive(Clone)]
struct Host {
    host_id: String,
    zone: String,
    owner: String,
    criticality: String,
}

#[derive(Clone)]
struct Identity {
    identity_id: String,
    owner: String,
    privilege_tier: String,
}

#[derive(Clone)]
struct Foothold {
    scenario_id: String,
    foothold_id: String,
    identity_id: String,
    host_id: String,
}

#[derive(Clone)]
struct Edge {
    edge_id: String,
    src_identity_id: String,
    src_host_id: String,
    dst_identity_id: String,
    dst_host_id: String,
    technique: String,
}

#[derive(Clone)]
struct Crown {
    crown_id: String,
    identity_id: String,
    host_id: String,
    impact_points: i64,
}

#[derive(Clone)]
struct Workflow {
    workflow_id: String,
    start_identity_id: String,
    start_host_id: String,
    end_identity_id: String,
    end_host_id: String,
    continuity_penalty_points: i64,
}

#[derive(Clone)]
struct Evidence {
    evidence_id: String,
    identity_id: String,
    host_id: String,
    value_points: i64,
}

#[derive(Clone)]
struct Node {
    identity_id: String,
    host_id: String,
    node_id: String,
}

#[derive(Clone)]
struct CaseData {
    params: Params,
    scenarios: Vec<Scenario>,
    approvals: Vec<Approval>,
    hosts: Vec<Host>,
    identities: Vec<Identity>,
    footholds: Vec<Foothold>,
    edges: Vec<Edge>,
    crowns: Vec<Crown>,
    workflows: Vec<Workflow>,
    evidence: Vec<Evidence>,
    nodes: Vec<Node>,
    approval_index: HashMap<String, usize>,
    owner_index: HashMap<String, usize>,
    host_index: HashMap<String, usize>,
    node_index: HashMap<String, usize>,
}

#[derive(Clone)]
struct DerivedAction {
    action_id: String,
    action_type: String,
    target_id: String,
    owner: String,
    disruption_points: i64,
    approval_ids: Vec<String>,
    captured_evidence_ids: Vec<String>,
    cleared_node_ids: Vec<String>,
    blocked_edge_ids: Vec<String>,
    approval_mask: u16,
    owner_mask: u16,
    captured_evidence_mask: u64,
    clear_node_mask: u64,
    clear_evidence_mask: u64,
    blocked_edge_mask: u64,
}

#[derive(Clone, Eq, PartialEq, Hash)]
struct SearchKey {
    wave_idx: usize,
    blocked_edge_mask: u64,
    approval_mask: u16,
    owner_mask: u16,
    captured_evidence_mask: u64,
    lost_evidence_mask: u64,
    comp_masks: Vec<u64>,
    lost_masks: Vec<u64>,
}

#[derive(Clone)]
struct TailResult {
    score_units: i64,
    review_minutes: i64,
    waves: Vec<Vec<usize>>,
}

#[derive(Clone)]
pub struct ScenarioOutput {
    scenario_id: String,
    protected_crown_ids: Vec<String>,
}

#[derive(Clone)]
pub struct ActionOutput {
    action_id: String,
    action_type: String,
    target_id: String,
    owner: String,
    disruption_points: i64,
    approval_ids: Vec<String>,
    captured_evidence_ids: Vec<String>,
    cleared_node_ids: Vec<String>,
    blocked_edge_ids: Vec<String>,
}

#[derive(Clone)]
pub struct WaveOutput {
    wave_index: usize,
    action_ids: Vec<String>,
    broken_workflow_ids: Vec<String>,
    actions: Vec<ActionOutput>,
}

#[derive(Clone)]
pub struct BestPlan {
    response_score_units: i64,
    total_disruption_points: i64,
    total_review_minutes: i64,
    preserved_evidence_points: i64,
    preserved_evidence_ids: Vec<String>,
    scenario_results: Vec<ScenarioOutput>,
    waves: Vec<WaveOutput>,
}

struct Solver {
    case: CaseData,
    actions: Vec<DerivedAction>,
    choices: Vec<Vec<usize>>,
    adjacency: Vec<Vec<(usize, usize)>>,
    review_sum_by_mask: Vec<i64>,
    owner_count_by_mask: Vec<usize>,
    crown_bits_by_row: Vec<u64>,
    evidence_bits_by_row: Vec<u64>,
    crown_union_mask: u64,
    total_evidence_mask: u64,
    initial_comp_masks: Vec<u64>,
    initial_lost_masks: Vec<u64>,
    workflow_cache: HashMap<u64, u64>,
    spread_cache: HashMap<(u64, u64), u64>,
    memo: HashMap<SearchKey, TailResult>,
}

fn die(message: &str) -> ! {
    panic!("{message}");
}

fn parse_i64(value: &str, context: &str) -> i64 {
    value
        .parse::<i64>()
        .unwrap_or_else(|_| die(&format!("invalid integer for {context}: {value}")))
}

fn bit(idx: usize, what: &str) -> u64 {
    if idx >= 64 {
        die(&format!("bitset overflow for {what}: expected fewer than 64 entries"));
    }
    1u64 << idx
}

fn approval_mask_bit(idx: usize) -> u16 {
    if idx >= 16 {
        die("approval/owner mask overflow: expected fewer than 16 entries");
    }
    1u16 << idx
}

fn json_escape(value: &str) -> String {
    value.replace('\\', "\\\\").replace('"', "\\\"")
}

fn json_string(value: &str) -> String {
    format!("\"{}\"", json_escape(value))
}

fn json_string_array(values: &[String]) -> String {
    format!(
        "[{}]",
        values
            .iter()
            .map(|value| json_string(value))
            .collect::<Vec<_>>()
            .join(",")
    )
}

fn sorted_node_ids(nodes: &[Node], mask: u64) -> Vec<String> {
    let mut out = Vec::new();
    for (idx, node) in nodes.iter().enumerate() {
        if mask & bit(idx, "node") != 0 {
            out.push(node.node_id.clone());
        }
    }
    out.sort();
    out
}

fn blocked_edge_ids(edges: &[Edge], mask: u64) -> Vec<String> {
    let mut out = Vec::new();
    for (idx, edge) in edges.iter().enumerate() {
        if mask & bit(idx, "edge") != 0 {
            out.push(edge.edge_id.clone());
        }
    }
    out
}

fn evidence_ids(evidence_rows: &[Evidence], mask: u64) -> Vec<String> {
    let mut out = Vec::new();
    for (idx, evidence) in evidence_rows.iter().enumerate() {
        if mask & bit(idx, "evidence") != 0 {
            out.push(evidence.evidence_id.clone());
        }
    }
    out
}

fn node_id(identity_id: &str, host_id: &str) -> String {
    format!("{identity_id}@{host_id}")
}

fn parse_case(path: &Path) -> CaseData {
    let text = fs::read_to_string(path).expect("read incident_case.txt");

    let mut wave_count = None;
    let mut max_actions_per_wave = None;
    let mut max_total_review_minutes = None;
    let mut min_distinct_owners = None;
    let mut min_preserved_evidence_points = None;

    let mut scenarios = Vec::new();
    let mut approvals = Vec::new();
    let mut hosts = Vec::new();
    let mut identities = Vec::new();
    let mut footholds = Vec::new();
    let mut edges = Vec::new();
    let mut crowns = Vec::new();
    let mut workflows = Vec::new();
    let mut evidence = Vec::new();

    let mut approval_index = HashMap::new();
    let mut owner_index = HashMap::new();
    let mut host_index = HashMap::new();
    let mut identity_index = HashMap::new();
    let mut scenario_index = HashMap::new();

    for raw_line in text.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let parts: Vec<&str> = line.split_whitespace().collect();
        match parts.as_slice() {
            ["PARAM", "file_version", _] => {}
            ["PARAM", "wave_count", value] => wave_count = Some(parse_i64(value, "wave_count") as usize),
            ["PARAM", "max_actions_per_wave", value] => {
                max_actions_per_wave = Some(parse_i64(value, "max_actions_per_wave") as usize)
            }
            ["PARAM", "max_total_review_minutes", value] => {
                max_total_review_minutes = Some(parse_i64(value, "max_total_review_minutes"))
            }
            ["PARAM", "min_distinct_owners", value] => {
                min_distinct_owners = Some(parse_i64(value, "min_distinct_owners") as usize)
            }
            ["PARAM", "min_preserved_evidence_points", value] => {
                min_preserved_evidence_points = Some(parse_i64(value, "min_preserved_evidence_points"))
            }
            ["SCENARIO", scenario_id, confidence_weight] => {
                if scenario_index
                    .insert((*scenario_id).to_string(), scenarios.len())
                    .is_some()
                {
                    die(&format!("duplicate scenario id: {scenario_id}"));
                }
                scenarios.push(Scenario {
                    scenario_id: (*scenario_id).to_string(),
                    confidence_weight: parse_i64(confidence_weight, "confidence_weight"),
                });
            }
            ["APPROVAL", approval_id, review_minutes] => {
                if approval_index
                    .insert((*approval_id).to_string(), approvals.len())
                    .is_some()
                {
                    die(&format!("duplicate approval id: {approval_id}"));
                }
                let owner = approval_id
                    .strip_prefix("APR_")
                    .unwrap_or_else(|| die(&format!("approval id must start with APR_: {approval_id}")));
                if !owner_index.contains_key(owner) {
                    let next_idx = owner_index.len();
                    owner_index.insert(owner.to_string(), next_idx);
                }
                approvals.push(Approval { review_minutes: parse_i64(review_minutes, "review_minutes") });
            }
            ["HOST", host_id, zone, owner, criticality] => {
                if host_index
                    .insert((*host_id).to_string(), hosts.len())
                    .is_some()
                {
                    die(&format!("duplicate host id: {host_id}"));
                }
                hosts.push(Host {
                    host_id: (*host_id).to_string(),
                    zone: (*zone).to_string(),
                    owner: (*owner).to_string(),
                    criticality: (*criticality).to_string(),
                });
            }
            ["IDENTITY", identity_id, owner, privilege_tier] => {
                if identity_index
                    .insert((*identity_id).to_string(), identities.len())
                    .is_some()
                {
                    die(&format!("duplicate identity id: {identity_id}"));
                }
                identities.push(Identity {
                    identity_id: (*identity_id).to_string(),
                    owner: (*owner).to_string(),
                    privilege_tier: (*privilege_tier).to_string(),
                });
            }
            ["FOOTHOLD", scenario_id, foothold_id, identity_id, host_id] => {
                footholds.push(Foothold {
                    scenario_id: (*scenario_id).to_string(),
                    foothold_id: (*foothold_id).to_string(),
                    identity_id: (*identity_id).to_string(),
                    host_id: (*host_id).to_string(),
                });
            }
            ["EDGE", edge_id, src_identity_id, src_host_id, dst_identity_id, dst_host_id, technique] => {
                edges.push(Edge {
                    edge_id: (*edge_id).to_string(),
                    src_identity_id: (*src_identity_id).to_string(),
                    src_host_id: (*src_host_id).to_string(),
                    dst_identity_id: (*dst_identity_id).to_string(),
                    dst_host_id: (*dst_host_id).to_string(),
                    technique: (*technique).to_string(),
                });
            }
            ["CROWN", crown_id, identity_id, host_id, impact_points] => {
                crowns.push(Crown {
                    crown_id: (*crown_id).to_string(),
                    identity_id: (*identity_id).to_string(),
                    host_id: (*host_id).to_string(),
                    impact_points: parse_i64(impact_points, "impact_points"),
                });
            }
            ["WORKFLOW", workflow_id, start_identity_id, start_host_id, end_identity_id, end_host_id, continuity_penalty_points] => {
                workflows.push(Workflow {
                    workflow_id: (*workflow_id).to_string(),
                    start_identity_id: (*start_identity_id).to_string(),
                    start_host_id: (*start_host_id).to_string(),
                    end_identity_id: (*end_identity_id).to_string(),
                    end_host_id: (*end_host_id).to_string(),
                    continuity_penalty_points: parse_i64(
                        continuity_penalty_points,
                        "continuity_penalty_points",
                    ),
                });
            }
            ["EVIDENCE", evidence_id, identity_id, host_id, value_points] => {
                evidence.push(Evidence {
                    evidence_id: (*evidence_id).to_string(),
                    identity_id: (*identity_id).to_string(),
                    host_id: (*host_id).to_string(),
                    value_points: parse_i64(value_points, "value_points"),
                });
            }
            _ => die(&format!("unrecognized row: {line}")),
        }
    }

    let params = Params {
        wave_count: wave_count.unwrap_or_else(|| die("missing PARAM wave_count")),
        max_actions_per_wave: max_actions_per_wave
            .unwrap_or_else(|| die("missing PARAM max_actions_per_wave")),
        max_total_review_minutes: max_total_review_minutes
            .unwrap_or_else(|| die("missing PARAM max_total_review_minutes")),
        min_distinct_owners: min_distinct_owners
            .unwrap_or_else(|| die("missing PARAM min_distinct_owners")),
        min_preserved_evidence_points: min_preserved_evidence_points
            .unwrap_or_else(|| die("missing PARAM min_preserved_evidence_points")),
    };

    if params.max_actions_per_wave != 2 {
        die("this task expects PARAM max_actions_per_wave 2");
    }
    if scenarios.is_empty() {
        die("expected at least one SCENARIO row");
    }
    if approvals.is_empty() || hosts.is_empty() || identities.is_empty() || edges.is_empty() {
        die("incident_case.txt is missing required inventory rows");
    }
    if evidence.is_empty() {
        die("expected at least one EVIDENCE row");
    }

    for host in &hosts {
        let approval_id = format!("APR_{}", host.owner);
        if !approval_index.contains_key(&approval_id) {
            die(&format!("missing approval row for host owner {}", host.owner));
        }
    }
    for identity in &identities {
        let approval_id = format!("APR_{}", identity.owner);
        if !approval_index.contains_key(&approval_id) {
            die(&format!("missing approval row for identity owner {}", identity.owner));
        }
    }
    if !approval_index.contains_key("APR_IR") {
        die("missing approval row for APR_IR");
    }
    if !owner_index.contains_key("IR") {
        let next_idx = owner_index.len();
        owner_index.insert("IR".to_string(), next_idx);
    }

    let mut nodes = Vec::new();
    let mut node_index = HashMap::new();
    let mut record_node = |identity_id: &str, host_id: &str| {
        if !identity_index.contains_key(identity_id) {
            die(&format!("unknown identity id in node reference: {identity_id}"));
        }
        if !host_index.contains_key(host_id) {
            die(&format!("unknown host id in node reference: {host_id}"));
        }
        let key = node_id(identity_id, host_id);
        if !node_index.contains_key(&key) {
            let idx = nodes.len();
            node_index.insert(key.clone(), idx);
            nodes.push(Node {
                identity_id: identity_id.to_string(),
                host_id: host_id.to_string(),
                node_id: key,
            });
        }
    };

    for foothold in &footholds {
        if !scenario_index.contains_key(&foothold.scenario_id) {
            die(&format!("unknown scenario id in foothold {}", foothold.foothold_id));
        }
        record_node(&foothold.identity_id, &foothold.host_id);
    }
    for edge in &edges {
        record_node(&edge.src_identity_id, &edge.src_host_id);
        record_node(&edge.dst_identity_id, &edge.dst_host_id);
    }
    for crown in &crowns {
        record_node(&crown.identity_id, &crown.host_id);
    }
    for workflow in &workflows {
        record_node(&workflow.start_identity_id, &workflow.start_host_id);
        record_node(&workflow.end_identity_id, &workflow.end_host_id);
    }
    for evidence_row in &evidence {
        record_node(&evidence_row.identity_id, &evidence_row.host_id);
    }

    if nodes.len() >= 64
        || edges.len() >= 64
        || crowns.len() >= 64
        || workflows.len() >= 64
        || evidence.len() >= 64
    {
        die("expected fewer than 64 nodes, edges, crowns, workflows, and evidence rows");
    }

    CaseData {
        params,
        scenarios,
        approvals,
        hosts,
        identities,
        footholds,
        edges,
        crowns,
        workflows,
        evidence,
        nodes,
        approval_index,
        owner_index,
        host_index,
        node_index,
    }
}

fn derive_actions(case: &CaseData) -> Vec<DerivedAction> {
    let credential_techniques = ["TOKEN_REUSE", "APPLOGIN", "OAUTH", "APIKEY"];
    let contain_techniques = ["WINRM", "RDP"];

    let mut actions = Vec::new();

    let ir_approval_id = "APR_IR".to_string();
    let ir_approval_mask = approval_mask_bit(case.approval_index[&ir_approval_id]);
    let ir_owner_mask = approval_mask_bit(case.owner_index["IR"]);

    for host in &case.hosts {
        let captured_evidence_mask = case
            .evidence
            .iter()
            .enumerate()
            .filter(|(_, row)| row.host_id == host.host_id)
            .fold(0u64, |mask, (idx, _)| mask | bit(idx, "evidence"));
        if captured_evidence_mask == 0 {
            continue;
        }
        let disruption_points = match host.criticality.as_str() {
            "STANDARD" => 1,
            "CRITICAL" => 2,
            other => die(&format!("unsupported criticality {other}")),
        };

        actions.push(DerivedAction {
            action_id: format!("ACT_SNAPSHOT_{}", host.host_id),
            action_type: "snapshot_host".to_string(),
            target_id: host.host_id.clone(),
            owner: "IR".to_string(),
            disruption_points,
            approval_ids: vec![ir_approval_id.clone()],
            captured_evidence_ids: evidence_ids(&case.evidence, captured_evidence_mask),
            cleared_node_ids: Vec::new(),
            blocked_edge_ids: Vec::new(),
            approval_mask: ir_approval_mask,
            owner_mask: ir_owner_mask,
            captured_evidence_mask,
            clear_node_mask: 0,
            clear_evidence_mask: 0,
            blocked_edge_mask: 0,
        });
    }

    for identity in &case.identities {
        let owner = identity.owner.clone();
        let approval_id = format!("APR_{owner}");
        let approval_mask = approval_mask_bit(case.approval_index[&approval_id]);
        let owner_mask = approval_mask_bit(case.owner_index[&owner]);
        let clear_mask = case
            .nodes
            .iter()
            .enumerate()
            .filter(|(_, node)| node.identity_id == identity.identity_id)
            .fold(0u64, |mask, (idx, _)| mask | bit(idx, "node"));
        let clear_evidence_mask = case
            .evidence
            .iter()
            .enumerate()
            .filter(|(_, row)| row.identity_id == identity.identity_id)
            .fold(0u64, |mask, (idx, _)| mask | bit(idx, "evidence"));
        let reset_edge_mask = case
            .edges
            .iter()
            .enumerate()
            .filter(|(_, edge)| {
                edge.src_identity_id == identity.identity_id
                    && credential_techniques.contains(&edge.technique.as_str())
            })
            .fold(0u64, |mask, (idx, _)| mask | bit(idx, "edge"));
        let disable_edge_mask = case
            .edges
            .iter()
            .enumerate()
            .filter(|(_, edge)| {
                edge.src_identity_id == identity.identity_id
                    || edge.dst_identity_id == identity.identity_id
            })
            .fold(0u64, |mask, (idx, _)| mask | bit(idx, "edge"));
        let reset_disruption = match identity.privilege_tier.as_str() {
            "USER" => 2,
            "SERVICE" => 3,
            "ADMIN" => 4,
            other => die(&format!("unsupported privilege_tier {other}")),
        };
        let disable_disruption = match identity.privilege_tier.as_str() {
            "USER" => 5,
            "SERVICE" => 6,
            "ADMIN" => 8,
            other => die(&format!("unsupported privilege_tier {other}")),
        };

        actions.push(DerivedAction {
            action_id: format!("ACT_RESET_{}", identity.identity_id),
            action_type: "reset_identity".to_string(),
            target_id: identity.identity_id.clone(),
            owner: owner.clone(),
            disruption_points: reset_disruption,
            approval_ids: vec![approval_id.clone()],
            captured_evidence_ids: Vec::new(),
            cleared_node_ids: Vec::new(),
            blocked_edge_ids: blocked_edge_ids(&case.edges, reset_edge_mask),
            approval_mask,
            owner_mask,
            captured_evidence_mask: 0,
            clear_node_mask: 0,
            clear_evidence_mask: 0,
            blocked_edge_mask: reset_edge_mask,
        });
        actions.push(DerivedAction {
            action_id: format!("ACT_DISABLE_{}", identity.identity_id),
            action_type: "disable_identity".to_string(),
            target_id: identity.identity_id.clone(),
            owner,
            disruption_points: disable_disruption,
            approval_ids: vec![approval_id],
            captured_evidence_ids: Vec::new(),
            cleared_node_ids: sorted_node_ids(&case.nodes, clear_mask),
            blocked_edge_ids: blocked_edge_ids(&case.edges, disable_edge_mask),
            approval_mask,
            owner_mask,
            captured_evidence_mask: 0,
            clear_node_mask: clear_mask,
            clear_evidence_mask,
            blocked_edge_mask: disable_edge_mask,
        });
    }

    for host in &case.hosts {
        let owner = host.owner.clone();
        let approval_id = format!("APR_{owner}");
        let approval_mask = approval_mask_bit(case.approval_index[&approval_id]);
        let owner_mask = approval_mask_bit(case.owner_index[&owner]);
        let clear_mask = case
            .nodes
            .iter()
            .enumerate()
            .filter(|(_, node)| node.host_id == host.host_id)
            .fold(0u64, |mask, (idx, _)| mask | bit(idx, "node"));
        let clear_evidence_mask = case
            .evidence
            .iter()
            .enumerate()
            .filter(|(_, row)| row.host_id == host.host_id)
            .fold(0u64, |mask, (idx, _)| mask | bit(idx, "evidence"));
        let contain_edge_mask = case
            .edges
            .iter()
            .enumerate()
            .filter(|(_, edge)| {
                edge.src_host_id == host.host_id
                    && contain_techniques.contains(&edge.technique.as_str())
            })
            .fold(0u64, |mask, (idx, _)| mask | bit(idx, "edge"));
        let isolate_edge_mask = case
            .edges
            .iter()
            .enumerate()
            .filter(|(_, edge)| edge.src_host_id == host.host_id || edge.dst_host_id == host.host_id)
            .fold(0u64, |mask, (idx, _)| mask | bit(idx, "edge"));
        let contain_disruption = match host.criticality.as_str() {
            "STANDARD" => 3,
            "CRITICAL" => 4,
            other => die(&format!("unsupported criticality {other}")),
        };
        let isolate_disruption = match host.criticality.as_str() {
            "STANDARD" => 6,
            "CRITICAL" => 8,
            other => die(&format!("unsupported criticality {other}")),
        };

        actions.push(DerivedAction {
            action_id: format!("ACT_CONTAIN_{}", host.host_id),
            action_type: "contain_host".to_string(),
            target_id: host.host_id.clone(),
            owner: owner.clone(),
            disruption_points: contain_disruption,
            approval_ids: vec![approval_id.clone()],
            captured_evidence_ids: Vec::new(),
            cleared_node_ids: Vec::new(),
            blocked_edge_ids: blocked_edge_ids(&case.edges, contain_edge_mask),
            approval_mask,
            owner_mask,
            captured_evidence_mask: 0,
            clear_node_mask: 0,
            clear_evidence_mask: 0,
            blocked_edge_mask: contain_edge_mask,
        });
        actions.push(DerivedAction {
            action_id: format!("ACT_ISOLATE_{}", host.host_id),
            action_type: "isolate_host".to_string(),
            target_id: host.host_id.clone(),
            owner,
            disruption_points: isolate_disruption,
            approval_ids: vec![approval_id],
            captured_evidence_ids: Vec::new(),
            cleared_node_ids: sorted_node_ids(&case.nodes, clear_mask),
            blocked_edge_ids: blocked_edge_ids(&case.edges, isolate_edge_mask),
            approval_mask,
            owner_mask,
            captured_evidence_mask: 0,
            clear_node_mask: clear_mask,
            clear_evidence_mask,
            blocked_edge_mask: isolate_edge_mask,
        });
    }

    actions.sort_by(|a, b| a.action_id.cmp(&b.action_id));
    actions
}

impl Solver {
    fn new(case: CaseData) -> Self {
        let actions = derive_actions(&case);
        let mut choices = Vec::new();
        choices.push(Vec::new());
        for idx in 0..actions.len() {
            choices.push(vec![idx]);
        }
        for left in 0..actions.len() {
            for right in (left + 1)..actions.len() {
                choices.push(vec![left, right]);
            }
        }

        let mut adjacency = vec![Vec::new(); case.nodes.len()];
        for (edge_idx, edge) in case.edges.iter().enumerate() {
            let src_key = node_id(&edge.src_identity_id, &edge.src_host_id);
            let dst_key = node_id(&edge.dst_identity_id, &edge.dst_host_id);
            let src_idx = case.node_index[&src_key];
            let dst_idx = case.node_index[&dst_key];
            adjacency[src_idx].push((dst_idx, edge_idx));
        }

        let approval_mask_size = 1usize << case.approvals.len();
        let mut review_sum_by_mask = vec![0i64; approval_mask_size];
        for mask in 1..approval_mask_size {
            let least_bit = mask & (!mask + 1);
            let bit_idx = least_bit.trailing_zeros() as usize;
            review_sum_by_mask[mask] = review_sum_by_mask[mask ^ least_bit]
                + case.approvals[bit_idx].review_minutes;
        }

        let owner_mask_size = 1usize << case.owner_index.len();
        let mut owner_count_by_mask = vec![0usize; owner_mask_size];
        for mask in 1..owner_mask_size {
            owner_count_by_mask[mask] = owner_count_by_mask[mask >> 1] + (mask & 1);
        }

        let mut crown_bits_by_row = Vec::new();
        let mut crown_union_mask = 0u64;
        for crown in &case.crowns {
            let key = node_id(&crown.identity_id, &crown.host_id);
            let node_idx = case.node_index[&key];
            let mask = bit(node_idx, "crown node");
            crown_bits_by_row.push(mask);
            crown_union_mask |= mask;
        }

        let mut evidence_bits_by_row = Vec::new();
        let mut total_evidence_mask = 0u64;
        for (evidence_idx, _) in case.evidence.iter().enumerate() {
            let mask = bit(evidence_idx, "evidence row");
            evidence_bits_by_row.push(mask);
            total_evidence_mask |= mask;
        }

        let mut initial_comp_masks = Vec::new();
        let mut initial_lost_masks = Vec::new();
        for scenario in &case.scenarios {
            let mut comp_mask = 0u64;
            for foothold in &case.footholds {
                if foothold.scenario_id == scenario.scenario_id {
                    let key = node_id(&foothold.identity_id, &foothold.host_id);
                    let node_idx = case.node_index[&key];
                    comp_mask |= bit(node_idx, "foothold node");
                }
            }
            initial_lost_masks.push(comp_mask & crown_union_mask);
            initial_comp_masks.push(comp_mask);
        }

        Self {
            case,
            actions,
            choices,
            adjacency,
            review_sum_by_mask,
            owner_count_by_mask,
            crown_bits_by_row,
            evidence_bits_by_row,
            crown_union_mask,
            total_evidence_mask,
            initial_comp_masks,
            initial_lost_masks,
            workflow_cache: HashMap::new(),
            spread_cache: HashMap::new(),
            memo: HashMap::new(),
        }
    }

    fn workflow_broken_mask(&mut self, blocked_edge_mask: u64) -> u64 {
        if let Some(existing) = self.workflow_cache.get(&blocked_edge_mask) {
            return *existing;
        }

        let mut broken_mask = 0u64;
        for (workflow_idx, workflow) in self.case.workflows.iter().enumerate() {
            let start_key = node_id(&workflow.start_identity_id, &workflow.start_host_id);
            let end_key = node_id(&workflow.end_identity_id, &workflow.end_host_id);
            let start_idx = self.case.node_index[&start_key];
            let end_idx = self.case.node_index[&end_key];
            let mut seen = vec![false; self.case.nodes.len()];
            let mut stack = vec![start_idx];
            seen[start_idx] = true;
            let mut reachable = false;
            while let Some(node_idx) = stack.pop() {
                if node_idx == end_idx {
                    reachable = true;
                    break;
                }
                for (next_idx, edge_idx) in &self.adjacency[node_idx] {
                    if blocked_edge_mask & bit(*edge_idx, "edge") != 0 || seen[*next_idx] {
                        continue;
                    }
                    seen[*next_idx] = true;
                    stack.push(*next_idx);
                }
            }
            if !reachable {
                broken_mask |= bit(workflow_idx, "workflow");
            }
        }

        self.workflow_cache.insert(blocked_edge_mask, broken_mask);
        broken_mask
    }

    fn spread_one_hop(&mut self, comp_mask: u64, blocked_edge_mask: u64) -> u64 {
        let cache_key = (comp_mask, blocked_edge_mask);
        if let Some(existing) = self.spread_cache.get(&cache_key) {
            return *existing;
        }
        let mut next_mask = comp_mask;
        for node_idx in 0..self.case.nodes.len() {
            if comp_mask & bit(node_idx, "node") == 0 {
                continue;
            }
            for (dst_idx, edge_idx) in &self.adjacency[node_idx] {
                if blocked_edge_mask & bit(*edge_idx, "edge") != 0 {
                    continue;
                }
                next_mask |= bit(*dst_idx, "node");
            }
        }
        self.spread_cache.insert(cache_key, next_mask);
        next_mask
    }

    fn protected_score(&self, lost_masks: &[u64]) -> i64 {
        let mut score = 0i64;
        for (scenario_idx, lost_mask) in lost_masks.iter().enumerate() {
            let weight = self.case.scenarios[scenario_idx].confidence_weight;
            for (crown_idx, crown) in self.case.crowns.iter().enumerate() {
                if lost_mask & self.crown_bits_by_row[crown_idx] == 0 {
                    score += weight * crown.impact_points * 100;
                }
            }
        }
        score
    }

    fn preserved_evidence_points(&self, lost_evidence_mask: u64) -> i64 {
        let mut points = 0i64;
        for (evidence_idx, row) in self.case.evidence.iter().enumerate() {
            if lost_evidence_mask & self.evidence_bits_by_row[evidence_idx] == 0 {
                points += row.value_points;
            }
        }
        points
    }

    fn evidence_score(&self, lost_evidence_mask: u64) -> i64 {
        self.preserved_evidence_points(lost_evidence_mask) * 25
    }

    fn schedule_cmp(&self, left: &[Vec<usize>], right: &[Vec<usize>]) -> Ordering {
        for (left_wave, right_wave) in left.iter().zip(right.iter()) {
            let len_cmp = left_wave.len().cmp(&right_wave.len());
            if len_cmp != Ordering::Equal {
                return len_cmp;
            }
            for (left_idx, right_idx) in left_wave.iter().zip(right_wave.iter()) {
                let cmp = self.actions[*left_idx]
                    .action_id
                    .cmp(&self.actions[*right_idx].action_id);
                if cmp != Ordering::Equal {
                    return cmp;
                }
            }
        }
        left.len().cmp(&right.len())
    }

    fn better(&self, candidate: &TailResult, incumbent: &TailResult) -> bool {
        if candidate.score_units != incumbent.score_units {
            return candidate.score_units > incumbent.score_units;
        }
        if candidate.review_minutes != incumbent.review_minutes {
            return candidate.review_minutes < incumbent.review_minutes;
        }
        self.schedule_cmp(&candidate.waves, &incumbent.waves) == Ordering::Less
    }

    fn solve(&mut self, key: SearchKey) -> TailResult {
        if let Some(existing) = self.memo.get(&key) {
            return existing.clone();
        }

        let result = if key.wave_idx == self.case.params.wave_count {
            let review_minutes = self.review_sum_by_mask[key.approval_mask as usize];
            let preserved_evidence_points = self.preserved_evidence_points(key.lost_evidence_mask);
            if review_minutes > self.case.params.max_total_review_minutes
                || self.owner_count_by_mask[key.owner_mask as usize]
                    < self.case.params.min_distinct_owners
                || preserved_evidence_points < self.case.params.min_preserved_evidence_points
            {
                TailResult {
                    score_units: NEG_INF,
                    review_minutes,
                    waves: Vec::new(),
                }
            } else {
                TailResult {
                    score_units: self.protected_score(&key.lost_masks)
                        + self.evidence_score(key.lost_evidence_mask),
                    review_minutes,
                    waves: Vec::new(),
                }
            }
        } else {
            let mut best: Option<TailResult> = None;
            let choices = self.choices.clone();
            for choice in choices {
                let mut blocked_edge_mask = key.blocked_edge_mask;
                let mut approval_mask = key.approval_mask;
                let mut owner_mask = key.owner_mask;
                let mut clear_node_mask = 0u64;
                let mut captured_evidence_mask = key.captured_evidence_mask;
                let mut clear_evidence_mask = 0u64;
                let mut disruption_points = 0i64;

                for action_idx in &choice {
                    let action = &self.actions[*action_idx];
                    blocked_edge_mask |= action.blocked_edge_mask;
                    approval_mask |= action.approval_mask;
                    owner_mask |= action.owner_mask;
                    clear_node_mask |= action.clear_node_mask;
                    captured_evidence_mask |= action.captured_evidence_mask;
                    clear_evidence_mask |= action.clear_evidence_mask;
                    disruption_points += action.disruption_points;
                }
                let lost_evidence_mask =
                    key.lost_evidence_mask | (clear_evidence_mask & !captured_evidence_mask);

                let mut next_comp_masks = Vec::with_capacity(key.comp_masks.len());
                let mut next_lost_masks = Vec::with_capacity(key.lost_masks.len());
                for (comp_mask, lost_mask) in key.comp_masks.iter().zip(key.lost_masks.iter()) {
                    let mut comp = comp_mask & !clear_node_mask;
                    comp = self.spread_one_hop(comp, blocked_edge_mask);
                    let lost = lost_mask | (comp & self.crown_union_mask);
                    next_comp_masks.push(comp);
                    next_lost_masks.push(lost);
                }

                let broken_mask = self.workflow_broken_mask(blocked_edge_mask);
                let mut workflow_penalty = 0i64;
                for (workflow_idx, workflow) in self.case.workflows.iter().enumerate() {
                    if broken_mask & bit(workflow_idx, "workflow") != 0 {
                        workflow_penalty += workflow.continuity_penalty_points * 10;
                    }
                }

                let next_key = SearchKey {
                    wave_idx: key.wave_idx + 1,
                    blocked_edge_mask,
                    approval_mask,
                    owner_mask,
                    captured_evidence_mask,
                    lost_evidence_mask,
                    comp_masks: next_comp_masks,
                    lost_masks: next_lost_masks,
                };
                let mut candidate = self.solve(next_key);
                if candidate.score_units == NEG_INF {
                    continue;
                }
                candidate.score_units -= workflow_penalty + disruption_points;
                candidate.waves.insert(0, choice);

                match &best {
                    Some(existing) if !self.better(&candidate, existing) => {}
                    _ => best = Some(candidate),
                }
            }

            best.unwrap_or(TailResult {
                score_units: NEG_INF,
                review_minutes: 0,
                waves: Vec::new(),
            })
        };

        self.memo.insert(key, result.clone());
        result
    }

    fn build_plan(&mut self, schedule: &[Vec<usize>]) -> BestPlan {
        let mut blocked_edge_mask = 0u64;
        let mut approval_mask = 0u16;
        let mut captured_evidence_mask = 0u64;
        let mut lost_evidence_mask = 0u64;
        let mut comp_masks = self.initial_comp_masks.clone();
        let mut lost_masks = self.initial_lost_masks.clone();
        let mut total_disruption_points = 0i64;
        let mut total_workflow_penalty = 0i64;
        let mut waves = Vec::new();
        let mut used_action_ids = HashMap::new();

        for (wave_idx, choice) in schedule.iter().enumerate() {
            let mut clear_node_mask = 0u64;
            let mut wave_clear_evidence_mask = 0u64;
            let mut action_ids = Vec::new();
            let mut actions = Vec::new();
            for action_idx in choice {
                let action = &self.actions[*action_idx];
                if used_action_ids.insert(action.action_id.clone(), ()).is_some() {
                    die("reference schedule unexpectedly reused an action id");
                }
                blocked_edge_mask |= action.blocked_edge_mask;
                approval_mask |= action.approval_mask;
                captured_evidence_mask |= action.captured_evidence_mask;
                clear_node_mask |= action.clear_node_mask;
                wave_clear_evidence_mask |= action.clear_evidence_mask;
                total_disruption_points += action.disruption_points;
                action_ids.push(action.action_id.clone());
                actions.push(ActionOutput {
                    action_id: action.action_id.clone(),
                    action_type: action.action_type.clone(),
                    target_id: action.target_id.clone(),
                    owner: action.owner.clone(),
                    disruption_points: action.disruption_points,
                    approval_ids: action.approval_ids.clone(),
                    captured_evidence_ids: action.captured_evidence_ids.clone(),
                    cleared_node_ids: action.cleared_node_ids.clone(),
                    blocked_edge_ids: action.blocked_edge_ids.clone(),
                });
            }
            lost_evidence_mask |= wave_clear_evidence_mask & !captured_evidence_mask;

            for scenario_idx in 0..comp_masks.len() {
                let mut comp = comp_masks[scenario_idx] & !clear_node_mask;
                comp = self.spread_one_hop(comp, blocked_edge_mask);
                comp_masks[scenario_idx] = comp;
                lost_masks[scenario_idx] |= comp & self.crown_union_mask;
            }

            let broken_mask = self.workflow_broken_mask(blocked_edge_mask);
            let mut broken_workflow_ids = Vec::new();
            for (workflow_idx, workflow) in self.case.workflows.iter().enumerate() {
                if broken_mask & bit(workflow_idx, "workflow") != 0 {
                    total_workflow_penalty += workflow.continuity_penalty_points * 10;
                    broken_workflow_ids.push(workflow.workflow_id.clone());
                }
            }

            waves.push(WaveOutput {
                wave_index: wave_idx + 1,
                action_ids,
                broken_workflow_ids,
                actions,
            });
        }

        let total_review_minutes = self.review_sum_by_mask[approval_mask as usize];
        let mut scenario_results = Vec::new();
        for (scenario_idx, scenario) in self.case.scenarios.iter().enumerate() {
            let mut protected_crown_ids = Vec::new();
            for (crown_idx, crown) in self.case.crowns.iter().enumerate() {
                if lost_masks[scenario_idx] & self.crown_bits_by_row[crown_idx] == 0 {
                    protected_crown_ids.push(crown.crown_id.clone());
                }
            }
            scenario_results.push(ScenarioOutput {
                scenario_id: scenario.scenario_id.clone(),
                protected_crown_ids,
            });
        }

        let preserved_evidence_points = self.preserved_evidence_points(lost_evidence_mask);
        let preserved_evidence_ids =
            evidence_ids(&self.case.evidence, self.total_evidence_mask & !lost_evidence_mask);

        BestPlan {
            response_score_units: self.protected_score(&lost_masks)
                + self.evidence_score(lost_evidence_mask)
                - total_workflow_penalty
                - total_disruption_points,
            total_disruption_points,
            total_review_minutes,
            preserved_evidence_points,
            preserved_evidence_ids,
            scenario_results,
            waves,
        }
    }
}

fn plan_to_json(plan: &BestPlan) -> String {
    let scenario_results = plan
        .scenario_results
        .iter()
        .map(|scenario| {
            format!(
                "{{\"scenario_id\":{},\"protected_crown_ids\":{}}}",
                json_string(&scenario.scenario_id),
                json_string_array(&scenario.protected_crown_ids)
            )
        })
        .collect::<Vec<_>>()
        .join(",");

    let waves = plan
        .waves
        .iter()
        .map(|wave| {
            let actions = wave
                .actions
                .iter()
                .map(|action| {
                    format!(
                        "{{\"action_id\":{},\"action_type\":{},\"target_id\":{},\"owner\":{},\"disruption_points\":{},\"approval_ids\":{},\"captured_evidence_ids\":{},\"cleared_node_ids\":{},\"blocked_edge_ids\":{}}}",
                        json_string(&action.action_id),
                        json_string(&action.action_type),
                        json_string(&action.target_id),
                        json_string(&action.owner),
                        action.disruption_points,
                        json_string_array(&action.approval_ids),
                        json_string_array(&action.captured_evidence_ids),
                        json_string_array(&action.cleared_node_ids),
                        json_string_array(&action.blocked_edge_ids)
                    )
                })
                .collect::<Vec<_>>()
                .join(",");

            format!(
                "{{\"wave_index\":{},\"action_ids\":{},\"broken_workflow_ids\":{},\"actions\":[{}]}}",
                wave.wave_index,
                json_string_array(&wave.action_ids),
                json_string_array(&wave.broken_workflow_ids),
                actions
            )
        })
        .collect::<Vec<_>>()
        .join(",");

    format!(
        "{{\"response_score_units\":{},\"total_disruption_points\":{},\"total_review_minutes\":{},\"preserved_evidence_points\":{},\"preserved_evidence_ids\":{},\"scenario_results\":[{}],\"waves\":[{}]}}",
        plan.response_score_units,
        plan.total_disruption_points,
        plan.total_review_minutes,
        plan.preserved_evidence_points,
        json_string_array(&plan.preserved_evidence_ids),
        scenario_results,
        waves
    )
}

pub fn solve_best_plan(path: &Path) -> BestPlan {
    let case = parse_case(path);
    let mut solver = Solver::new(case);
    let key = SearchKey {
        wave_idx: 0,
        blocked_edge_mask: 0,
        approval_mask: 0,
        owner_mask: 0,
        captured_evidence_mask: 0,
        lost_evidence_mask: 0,
        comp_masks: solver.initial_comp_masks.clone(),
        lost_masks: solver.initial_lost_masks.clone(),
    };
    let best = solver.solve(key);
    if best.score_units == NEG_INF {
        die("no feasible containment schedule found");
    }
    solver.build_plan(&best.waves)
}

pub fn solve_to_json(path: &Path) -> String {
    plan_to_json(&solve_best_plan(path))
}
