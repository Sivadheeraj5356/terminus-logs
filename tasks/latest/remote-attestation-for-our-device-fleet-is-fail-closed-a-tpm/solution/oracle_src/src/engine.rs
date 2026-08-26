//! Complete attestation verification engine matching the Python reference.

use std::collections::{BTreeSet, HashMap};
use std::path::Path;

use p256::ecdsa::signature::Verifier;

use crate::appraise::appraise;
use crate::crypto_helpers::{
    fingerprint_public_key_sec1, parse_sec1_verifying_key, sha256, signature_from_raw_rs,
};
use crate::hexutil::{decode_lower_hex, encode_lower_hex};
use crate::load::{load_dataset, AttestationKey, Dataset, Event, EventLog, Request};
use crate::models::{
    ConflictRow, CounterRow, EventRow, NonceRow, PcrRow, QuoteRow, ReferenceMatchRow, Report,
    RequestRow, Summary,
};
use crate::quote_parse::{
    magic_hex, parse_quote, parse_signature, ParsedQuote, ATTEST_QUOTE, MAGIC, SUPPORTED_PCRS,
};

#[derive(Clone)]
struct DeviceState {
    reset_count: u32,
    restart_count: u32,
    clock: u64,
}

fn conflict(
    request_id: &str,
    conflict_type: &str,
    subject: &str,
    reason: &str,
    related: &[String],
) -> ConflictRow {
    let related_values: Vec<String> = related
        .iter()
        .cloned()
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    ConflictRow {
        request_id: request_id.to_string(),
        conflict_type: conflict_type.to_string(),
        subject: subject.to_string(),
        reason_code: reason.to_string(),
        related_values,
    }
}

fn reject_row(
    req: &Request,
    reason: &str,
    nonce_consumed: bool,
    counter_committed: bool,
    selected_pcr_count: u32,
    replayed_event_count: u32,
    matched_rule_count: u32,
    failed_rule_count: u32,
) -> RequestRow {
    RequestRow {
        request_id: req.request_id.clone(),
        received_at: req.received_at,
        device_id: req.device_id.clone(),
        status: "rejected".into(),
        reason_or_null: Some(reason.to_string()),
        nonce_consumed_by_this_request: nonce_consumed,
        selected_pcr_count,
        replayed_event_count,
        matched_rule_count,
        failed_rule_count,
        counter_committed,
    }
}

fn quote_row(
    rid: &str,
    key: &AttestationKey,
    fp: &str,
    quote: &ParsedQuote,
    sig_status: &str,
    pcr_status: &str,
    computed_hex: Option<String>,
) -> QuoteRow {
    QuoteRow {
        request_id: rid.to_string(),
        attestation_key_id: key.attestation_key_id.clone(),
        attestation_key_fingerprint: fp.to_string(),
        magic_hex: magic_hex(quote.magic),
        attestation_type: "quote".into(),
        qualified_signer_hex: encode_lower_hex(&quote.qualified_signer),
        extra_data_hex: encode_lower_hex(&quote.extra_data),
        clock: quote.clock,
        reset_count: quote.reset_count,
        restart_count: quote.restart_count,
        safe: quote.safe,
        firmware_version: quote.firmware_version,
        selected_pcrs: quote.selected_pcrs.clone(),
        quoted_pcr_digest: encode_lower_hex(&quote.pcr_digest),
        computed_pcr_digest_or_null: computed_hex,
        signature_status: sig_status.to_string(),
        pcr_digest_status: pcr_status.to_string(),
    }
}

fn counter_not_checked(
    counter_rows: &mut Vec<CounterRow>,
    rid: &str,
    req: &Request,
    device_state: &HashMap<String, DeviceState>,
    quote: &ParsedQuote,
) {
    let prior = &device_state[&req.device_id];
    counter_rows.push(CounterRow {
        request_id: rid.to_string(),
        device_id: req.device_id.clone(),
        prior_reset_count: prior.reset_count,
        prior_restart_count: prior.restart_count,
        prior_clock: prior.clock,
        quoted_reset_count: quote.reset_count,
        quoted_restart_count: quote.restart_count,
        quoted_clock: quote.clock,
        safe: quote.safe,
        status: "not_checked".into(),
        committed: false,
    });
}

fn zero_pcrs() -> HashMap<u32, Vec<u8>> {
    SUPPORTED_PCRS
        .iter()
        .map(|&p| (p, vec![0u8; 32]))
        .collect()
}

fn replay_events(events: &[Event]) -> HashMap<u32, Vec<u8>> {
    let mut pcrs = zero_pcrs();
    let mut ordered: Vec<&Event> = events.iter().collect();
    ordered.sort_by_key(|e| e.event_seq);
    for ev in ordered {
        let digest = decode_lower_hex(&ev.measurement_digest).expect("validated digest");
        let cur = pcrs.get(&ev.pcr_index).expect("supported pcr").clone();
        let mut buf = cur;
        buf.extend_from_slice(&digest);
        pcrs.insert(ev.pcr_index, sha256(&buf).to_vec());
    }
    pcrs
}

fn selected_pcr_digest(pcrs: &HashMap<u32, Vec<u8>>, selected: &[u32]) -> Vec<u8> {
    let mut idxs: Vec<u32> = selected.to_vec();
    idxs.sort_unstable();
    let mut parts = Vec::new();
    for i in idxs {
        parts.extend_from_slice(&pcrs[&i]);
    }
    sha256(&parts).to_vec()
}

fn verify_sig(pub_sec1: &[u8], quote_raw: &[u8], r: &[u8], s: &[u8]) -> bool {
    let Ok(vk) = parse_sec1_verifying_key(pub_sec1) else {
        return false;
    };
    let Ok(sig) = signature_from_raw_rs(r, s) else {
        return false;
    };
    vk.verify(quote_raw, &sig).is_ok()
}

fn emit_events_not_evaluated(
    event_rows: &mut Vec<EventRow>,
    rid: &str,
    elog: &EventLog,
) {
    let mut evs: Vec<&Event> = elog.events.iter().collect();
    evs.sort_by_key(|e| e.event_seq);
    for ev in evs {
        event_rows.push(EventRow {
            request_id: rid.to_string(),
            event_log_id: elog.event_log_id.clone(),
            event_seq: ev.event_seq,
            pcr_index: ev.pcr_index,
            event_type: ev.event_type.clone(),
            component: ev.component.clone(),
            version: ev.version.clone(),
            measurement_digest: ev.measurement_digest.clone(),
            policy_status: "not_evaluated".into(),
            matched_rule_id_or_null: None,
        });
    }
}

fn process_one(
    ds: &Dataset,
    req: &Request,
    device_state: &mut HashMap<String, DeviceState>,
    nonce_consumed: &mut HashMap<String, Option<String>>,
    quote_rows: &mut Vec<QuoteRow>,
    event_rows: &mut Vec<EventRow>,
    pcr_rows: &mut Vec<PcrRow>,
    reference_match_rows: &mut Vec<ReferenceMatchRow>,
    counter_rows: &mut Vec<CounterRow>,
    conflict_rows: &mut Vec<ConflictRow>,
) -> RequestRow {
    let rid = req.request_id.as_str();

    // 1 device
    if !ds.devices.contains_key(&req.device_id) {
        conflict_rows.push(conflict(
            rid,
            "identity",
            &req.device_id,
            "device_unknown",
            &[req.device_id.clone()],
        ));
        return reject_row(req, "device_unknown", false, false, 0, 0, 0, 0);
    }

    // 2 key
    if !ds.keys.contains_key(&req.attestation_key_id) {
        conflict_rows.push(conflict(
            rid,
            "identity",
            &req.attestation_key_id,
            "attestation_key_unknown",
            &[req.attestation_key_id.clone()],
        ));
        return reject_row(req, "attestation_key_unknown", false, false, 0, 0, 0, 0);
    }

    // 3 nonce
    if !ds.nonces.contains_key(&req.nonce_id) {
        conflict_rows.push(conflict(
            rid,
            "nonce",
            &req.nonce_id,
            "nonce_unknown",
            &[req.nonce_id.clone()],
        ));
        return reject_row(req, "nonce_unknown", false, false, 0, 0, 0, 0);
    }

    // 4 policy
    if !ds.policies.contains_key(&req.policy_id) {
        conflict_rows.push(conflict(
            rid,
            "identity",
            &req.policy_id,
            "reference_policy_unknown",
            &[req.policy_id.clone()],
        ));
        return reject_row(req, "reference_policy_unknown", false, false, 0, 0, 0, 0);
    }

    // 5 event log
    if !ds.event_logs.contains_key(&req.event_log_id) {
        conflict_rows.push(conflict(
            rid,
            "identity",
            &req.event_log_id,
            "event_log_unknown",
            &[req.event_log_id.clone()],
        ));
        return reject_row(req, "event_log_unknown", false, false, 0, 0, 0, 0);
    }

    let device = &ds.devices[&req.device_id];
    let key = &ds.keys[&req.attestation_key_id];
    let nonce = &ds.nonces[&req.nonce_id];
    let policy = &ds.policies[&req.policy_id];
    let elog = &ds.event_logs[&req.event_log_id];

    // 6 key belongs to device
    if key.device_id != req.device_id {
        conflict_rows.push(conflict(
            rid,
            "identity",
            &req.attestation_key_id,
            "attestation_key_device_mismatch",
            &[key.device_id.clone(), req.device_id.clone()],
        ));
        return reject_row(
            req,
            "attestation_key_device_mismatch",
            false,
            false,
            0,
            0,
            0,
            0,
        );
    }

    // 7 device class allowed
    if !policy
        .allowed_device_classes
        .iter()
        .any(|c| c == &device.device_class)
    {
        conflict_rows.push(conflict(
            rid,
            "identity",
            &device.device_class,
            "device_class_not_allowed",
            &[device.device_class.clone(), req.policy_id.clone()],
        ));
        return reject_row(req, "device_class_not_allowed", false, false, 0, 0, 0, 0);
    }

    // 8 quote parse
    let quote = match parse_quote(&req.quote_bytes) {
        Ok(q) => q,
        Err(_) => return reject_row(req, "quote_malformed", false, false, 0, 0, 0, 0),
    };

    let fp = fingerprint_public_key_sec1(&key.public_key_sec1);

    // 9 signature parse
    let sig = match parse_signature(&req.signature_bytes) {
        Ok(s) => s,
        Err(_) => {
            quote_rows.push(QuoteRow {
                request_id: rid.to_string(),
                attestation_key_id: key.attestation_key_id.clone(),
                attestation_key_fingerprint: fp.clone(),
                magic_hex: magic_hex(quote.magic),
                attestation_type: "quote".into(),
                qualified_signer_hex: encode_lower_hex(&quote.qualified_signer),
                extra_data_hex: encode_lower_hex(&quote.extra_data),
                clock: quote.clock,
                reset_count: quote.reset_count,
                restart_count: quote.restart_count,
                safe: quote.safe,
                firmware_version: quote.firmware_version,
                selected_pcrs: quote.selected_pcrs.clone(),
                quoted_pcr_digest: encode_lower_hex(&quote.pcr_digest),
                computed_pcr_digest_or_null: None,
                signature_status: "not_checked".into(),
                pcr_digest_status: "not_checked".into(),
            });
            let prior = &device_state[&req.device_id];
            counter_rows.push(CounterRow {
                request_id: rid.to_string(),
                device_id: req.device_id.clone(),
                prior_reset_count: prior.reset_count,
                prior_restart_count: prior.restart_count,
                prior_clock: prior.clock,
                quoted_reset_count: quote.reset_count,
                quoted_restart_count: quote.restart_count,
                quoted_clock: quote.clock,
                safe: quote.safe,
                status: "not_checked".into(),
                committed: false,
            });
            return reject_row(req, "signature_malformed", false, false, 0, 0, 0, 0);
        }
    };

    // 10 magic
    if quote.magic != MAGIC {
        quote_rows.push(quote_row(
            rid,
            key,
            &fp,
            &quote,
            "not_checked",
            "not_checked",
            None,
        ));
        counter_not_checked(counter_rows, rid, req, device_state, &quote);
        let mh = magic_hex(quote.magic);
        conflict_rows.push(conflict(
            rid,
            "identity",
            &mh,
            "quote_magic_invalid",
            &[mh.clone()],
        ));
        return reject_row(req, "quote_magic_invalid", false, false, 0, 0, 0, 0);
    }

    // 11 type
    if quote.attestation_type != ATTEST_QUOTE {
        quote_rows.push(quote_row(
            rid,
            key,
            &fp,
            &quote,
            "not_checked",
            "not_checked",
            None,
        ));
        counter_not_checked(counter_rows, rid, req, device_state, &quote);
        let typ = format!("0x{:04x}", quote.attestation_type);
        conflict_rows.push(conflict(
            rid,
            "identity",
            &typ,
            "quote_type_invalid",
            &[typ.clone()],
        ));
        return reject_row(req, "quote_type_invalid", false, false, 0, 0, 0, 0);
    }

    // 12 qualified signer
    if quote.qualified_signer != key.qualified_name {
        quote_rows.push(quote_row(
            rid,
            key,
            &fp,
            &quote,
            "not_checked",
            "not_checked",
            None,
        ));
        counter_not_checked(counter_rows, rid, req, device_state, &quote);
        conflict_rows.push(conflict(
            rid,
            "identity",
            &key.attestation_key_id,
            "qualified_signer_mismatch",
            &[
                encode_lower_hex(&quote.qualified_signer),
                key.qualified_name_hex.clone(),
            ],
        ));
        return reject_row(req, "qualified_signer_mismatch", false, false, 0, 0, 0, 0);
    }

    // 13 key validity
    if !(key.valid_from <= req.received_at && req.received_at <= key.valid_until) {
        quote_rows.push(quote_row(
            rid,
            key,
            &fp,
            &quote,
            "not_checked",
            "not_checked",
            None,
        ));
        counter_not_checked(counter_rows, rid, req, device_state, &quote);
        conflict_rows.push(conflict(
            rid,
            "identity",
            &key.attestation_key_id,
            "attestation_key_not_valid",
            &[
                req.received_at.to_string(),
                key.valid_from.to_string(),
                key.valid_until.to_string(),
            ],
        ));
        return reject_row(req, "attestation_key_not_valid", false, false, 0, 0, 0, 0);
    }

    // 14 signature verify
    let sig_ok = verify_sig(&key.public_key_sec1, &quote.raw, &sig.r, &sig.s);
    if !sig_ok {
        quote_rows.push(quote_row(
            rid,
            key,
            &fp,
            &quote,
            "invalid",
            "not_checked",
            None,
        ));
        counter_not_checked(counter_rows, rid, req, device_state, &quote);
        conflict_rows.push(conflict(
            rid,
            "identity",
            &key.attestation_key_id,
            "quote_signature_invalid",
            &[key.attestation_key_id.clone()],
        ));
        return reject_row(req, "quote_signature_invalid", false, false, 0, 0, 0, 0);
    }

    // 15 nonce device
    if nonce.device_id != req.device_id {
        quote_rows.push(quote_row(rid, key, &fp, &quote, "valid", "not_checked", None));
        counter_not_checked(counter_rows, rid, req, device_state, &quote);
        conflict_rows.push(conflict(
            rid,
            "nonce",
            &nonce.nonce_id,
            "nonce_device_mismatch",
            &[nonce.device_id.clone(), req.device_id.clone()],
        ));
        return reject_row(req, "nonce_device_mismatch", false, false, 0, 0, 0, 0);
    }

    // 16 not yet valid
    if req.received_at < nonce.issued_at {
        quote_rows.push(quote_row(rid, key, &fp, &quote, "valid", "not_checked", None));
        counter_not_checked(counter_rows, rid, req, device_state, &quote);
        conflict_rows.push(conflict(
            rid,
            "nonce",
            &nonce.nonce_id,
            "nonce_not_yet_valid",
            &[req.received_at.to_string(), nonce.issued_at.to_string()],
        ));
        return reject_row(req, "nonce_not_yet_valid", false, false, 0, 0, 0, 0);
    }

    // 17 expired
    if req.received_at > nonce.expires_at {
        quote_rows.push(quote_row(rid, key, &fp, &quote, "valid", "not_checked", None));
        counter_not_checked(counter_rows, rid, req, device_state, &quote);
        conflict_rows.push(conflict(
            rid,
            "nonce",
            &nonce.nonce_id,
            "nonce_expired",
            &[req.received_at.to_string(), nonce.expires_at.to_string()],
        ));
        return reject_row(req, "nonce_expired", false, false, 0, 0, 0, 0);
    }

    // 18 consumed
    if nonce_consumed[&nonce.nonce_id].is_some() {
        quote_rows.push(quote_row(rid, key, &fp, &quote, "valid", "not_checked", None));
        counter_not_checked(counter_rows, rid, req, device_state, &quote);
        let consumer = nonce_consumed[&nonce.nonce_id].clone().unwrap();
        conflict_rows.push(conflict(
            rid,
            "nonce",
            &nonce.nonce_id,
            "nonce_consumed",
            &[consumer],
        ));
        return reject_row(req, "nonce_consumed", false, false, 0, 0, 0, 0);
    }

    // 19 extra_data match
    if quote.extra_data != nonce.nonce_bytes {
        quote_rows.push(quote_row(rid, key, &fp, &quote, "valid", "not_checked", None));
        counter_not_checked(counter_rows, rid, req, device_state, &quote);
        conflict_rows.push(conflict(
            rid,
            "nonce",
            &nonce.nonce_id,
            "nonce_mismatch",
            &[
                encode_lower_hex(&quote.extra_data),
                nonce.nonce_hex.clone(),
            ],
        ));
        return reject_row(req, "nonce_mismatch", false, false, 0, 0, 0, 0);
    }

    // CONSUME NONCE
    nonce_consumed.insert(nonce.nonce_id.clone(), Some(rid.to_string()));

    // 20 PCR selection vs policy
    if quote.selected_pcrs != policy.required_pcrs {
        quote_rows.push(quote_row(rid, key, &fp, &quote, "valid", "not_checked", None));
        counter_not_checked(counter_rows, rid, req, device_state, &quote);
        let qs: Vec<String> = quote.selected_pcrs.iter().map(|p| p.to_string()).collect();
        let ps: Vec<String> = policy.required_pcrs.iter().map(|p| p.to_string()).collect();
        conflict_rows.push(conflict(
            rid,
            "pcr",
            &req.policy_id,
            "quote_pcr_selection_invalid",
            &[qs.join(","), ps.join(",")],
        ));
        return reject_row(req, "quote_pcr_selection_invalid", true, false, 0, 0, 0, 0);
    }

    // 21 event log device
    if elog.device_id != req.device_id {
        quote_rows.push(quote_row(rid, key, &fp, &quote, "valid", "not_checked", None));
        counter_not_checked(counter_rows, rid, req, device_state, &quote);
        conflict_rows.push(conflict(
            rid,
            "pcr",
            &elog.event_log_id,
            "event_log_device_mismatch",
            &[elog.device_id.clone(), req.device_id.clone()],
        ));
        return reject_row(req, "event_log_device_mismatch", true, false, 0, 0, 0, 0);
    }

    // Replay PCRs
    let pcrs = replay_events(&elog.events);
    let computed = selected_pcr_digest(&pcrs, &quote.selected_pcrs);
    let computed_hex = encode_lower_hex(&computed);
    let replayed_event_count = elog.events.len() as u32;
    let selected_pcr_count = quote.selected_pcrs.len() as u32;

    for &pcr_index in &SUPPORTED_PCRS {
        pcr_rows.push(PcrRow {
            request_id: rid.to_string(),
            pcr_index,
            selected: quote.selected_pcrs.contains(&pcr_index),
            policy_required: policy.required_pcrs.contains(&pcr_index),
            replayed_value: encode_lower_hex(&pcrs[&pcr_index]),
        });
    }

    // 22 digest match
    if computed != quote.pcr_digest {
        quote_rows.push(quote_row(
            rid,
            key,
            &fp,
            &quote,
            "valid",
            "mismatched",
            Some(computed_hex.clone()),
        ));
        emit_events_not_evaluated(event_rows, rid, elog);
        counter_not_checked(counter_rows, rid, req, device_state, &quote);
        conflict_rows.push(conflict(
            rid,
            "pcr",
            &elog.event_log_id,
            "pcr_digest_mismatch",
            &[
                encode_lower_hex(&quote.pcr_digest),
                computed_hex,
            ],
        ));
        return reject_row(
            req,
            "pcr_digest_mismatch",
            true,
            false,
            selected_pcr_count,
            replayed_event_count,
            0,
            0,
        );
    }

    // 23 safe clock
    let prior = device_state[&req.device_id].clone();
    if policy.require_safe && quote.safe != 1 {
        quote_rows.push(quote_row(
            rid,
            key,
            &fp,
            &quote,
            "valid",
            "matched",
            Some(computed_hex.clone()),
        ));
        emit_events_not_evaluated(event_rows, rid, elog);
        counter_rows.push(CounterRow {
            request_id: rid.to_string(),
            device_id: req.device_id.clone(),
            prior_reset_count: prior.reset_count,
            prior_restart_count: prior.restart_count,
            prior_clock: prior.clock,
            quoted_reset_count: quote.reset_count,
            quoted_restart_count: quote.restart_count,
            quoted_clock: quote.clock,
            safe: quote.safe,
            status: "unsafe".into(),
            committed: false,
        });
        conflict_rows.push(conflict(
            rid,
            "counter",
            &req.device_id,
            "clock_unsafe",
            &[quote.safe.to_string()],
        ));
        return reject_row(
            req,
            "clock_unsafe",
            true,
            false,
            selected_pcr_count,
            replayed_event_count,
            0,
            0,
        );
    }

    // 24 counter monotonicity
    let mut rollback = false;
    if quote.reset_count < prior.reset_count {
        rollback = true;
    } else if quote.reset_count == prior.reset_count
        && quote.restart_count < prior.restart_count
    {
        rollback = true;
    } else if quote.reset_count == prior.reset_count
        && quote.restart_count == prior.restart_count
        && quote.clock < prior.clock
    {
        rollback = true;
    }

    if rollback {
        quote_rows.push(quote_row(
            rid,
            key,
            &fp,
            &quote,
            "valid",
            "matched",
            Some(computed_hex.clone()),
        ));
        emit_events_not_evaluated(event_rows, rid, elog);
        counter_rows.push(CounterRow {
            request_id: rid.to_string(),
            device_id: req.device_id.clone(),
            prior_reset_count: prior.reset_count,
            prior_restart_count: prior.restart_count,
            prior_clock: prior.clock,
            quoted_reset_count: quote.reset_count,
            quoted_restart_count: quote.restart_count,
            quoted_clock: quote.clock,
            safe: quote.safe,
            status: "rollback".into(),
            committed: false,
        });
        conflict_rows.push(conflict(
            rid,
            "counter",
            &req.device_id,
            "counter_rollback",
            &[
                prior.reset_count.to_string(),
                prior.restart_count.to_string(),
                prior.clock.to_string(),
                quote.reset_count.to_string(),
                quote.restart_count.to_string(),
                quote.clock.to_string(),
            ],
        ));
        return reject_row(
            req,
            "counter_rollback",
            true,
            false,
            selected_pcr_count,
            replayed_event_count,
            0,
            0,
        );
    }

    // COMMIT COUNTERS
    device_state.insert(
        req.device_id.clone(),
        DeviceState {
            reset_count: quote.reset_count,
            restart_count: quote.restart_count,
            clock: quote.clock,
        },
    );

    // 25 firmware
    if !policy
        .allowed_firmware_versions
        .iter()
        .any(|&v| v == quote.firmware_version)
    {
        quote_rows.push(quote_row(
            rid,
            key,
            &fp,
            &quote,
            "valid",
            "matched",
            Some(computed_hex.clone()),
        ));
        emit_events_not_evaluated(event_rows, rid, elog);
        counter_rows.push(CounterRow {
            request_id: rid.to_string(),
            device_id: req.device_id.clone(),
            prior_reset_count: prior.reset_count,
            prior_restart_count: prior.restart_count,
            prior_clock: prior.clock,
            quoted_reset_count: quote.reset_count,
            quoted_restart_count: quote.restart_count,
            quoted_clock: quote.clock,
            safe: quote.safe,
            status: "accepted".into(),
            committed: true,
        });
        conflict_rows.push(conflict(
            rid,
            "firmware",
            &quote.firmware_version.to_string(),
            "firmware_not_allowed",
            &[quote.firmware_version.to_string()],
        ));
        return reject_row(
            req,
            "firmware_not_allowed",
            true,
            true,
            selected_pcr_count,
            replayed_event_count,
            0,
            0,
        );
    }

    // Reference appraisal (26/27)
    let appraisal = appraise(policy, &elog.events);
    for rr in &appraisal.rule_results {
        reference_match_rows.push(ReferenceMatchRow {
            request_id: rid.to_string(),
            policy_id: policy.policy_id.clone(),
            rule_id: rr.rule_id.clone(),
            rule_kind: rr.rule_kind.clone(),
            matched_event_sequences: rr.matched_event_sequences.clone(),
            status: rr.status.clone(),
            reason_or_null: rr.reason_or_null.clone(),
        });
    }

    let mut evs: Vec<&Event> = elog.events.iter().collect();
    evs.sort_by_key(|e| e.event_seq);
    for ev in evs {
        let (st, mrid) = appraisal
            .event_policy_status
            .get(&ev.event_seq)
            .cloned()
            .unwrap_or_else(|| ("not_evaluated".into(), None));
        event_rows.push(EventRow {
            request_id: rid.to_string(),
            event_log_id: elog.event_log_id.clone(),
            event_seq: ev.event_seq,
            pcr_index: ev.pcr_index,
            event_type: ev.event_type.clone(),
            component: ev.component.clone(),
            version: ev.version.clone(),
            measurement_digest: ev.measurement_digest.clone(),
            policy_status: st,
            matched_rule_id_or_null: mrid,
        });
    }

    quote_rows.push(quote_row(
        rid,
        key,
        &fp,
        &quote,
        "valid",
        "matched",
        Some(computed_hex),
    ));
    counter_rows.push(CounterRow {
        request_id: rid.to_string(),
        device_id: req.device_id.clone(),
        prior_reset_count: prior.reset_count,
        prior_restart_count: prior.restart_count,
        prior_clock: prior.clock,
        quoted_reset_count: quote.reset_count,
        quoted_restart_count: quote.restart_count,
        quoted_clock: quote.clock,
        safe: quote.safe,
        status: "accepted".into(),
        committed: true,
    });

    if let Some(ref reason) = appraisal.reject_reason {
        let ctype = if reason == "event_order_violation" {
            "event_order"
        } else {
            "measurement"
        };
        let (subject, related) = if let Some((a, b)) = &appraisal.order_failed {
            (format!("{a}->{b}"), vec![a.clone(), b.clone()])
        } else {
            (req.policy_id.clone(), vec![req.policy_id.clone()])
        };
        conflict_rows.push(conflict(rid, ctype, &subject, reason, &related));
        return reject_row(
            req,
            reason,
            true,
            true,
            selected_pcr_count,
            replayed_event_count,
            appraisal.matched_rule_count,
            appraisal.failed_rule_count,
        );
    }

    RequestRow {
        request_id: rid.to_string(),
        received_at: req.received_at,
        device_id: req.device_id.clone(),
        status: "accepted".into(),
        reason_or_null: None,
        nonce_consumed_by_this_request: true,
        selected_pcr_count,
        replayed_event_count,
        matched_rule_count: appraisal.matched_rule_count,
        failed_rule_count: appraisal.failed_rule_count,
        counter_committed: true,
    }
}

fn verify_dataset(ds: Dataset) -> Report {
    let mut device_state: HashMap<String, DeviceState> = ds
        .devices
        .iter()
        .map(|(did, d)| {
            (
                did.clone(),
                DeviceState {
                    reset_count: d.last_reset_count,
                    restart_count: d.last_restart_count,
                    clock: d.last_clock,
                },
            )
        })
        .collect();

    let mut nonce_consumed: HashMap<String, Option<String>> = ds
        .nonces
        .iter()
        .map(|(nid, n)| {
            (
                nid.clone(),
                n.initially_consumed_by_request_id_or_null.clone(),
            )
        })
        .collect();

    let mut request_rows = Vec::new();
    let mut quote_rows = Vec::new();
    let mut event_rows = Vec::new();
    let mut pcr_rows = Vec::new();
    let mut reference_match_rows = Vec::new();
    let mut counter_rows = Vec::new();
    let mut conflict_rows = Vec::new();

    let mut ordered_reqs = ds.requests.clone();
    ordered_reqs.sort_by(|a, b| {
        (a.received_at, &a.request_id).cmp(&(b.received_at, &b.request_id))
    });

    for req in &ordered_reqs {
        let result = process_one(
            &ds,
            req,
            &mut device_state,
            &mut nonce_consumed,
            &mut quote_rows,
            &mut event_rows,
            &mut pcr_rows,
            &mut reference_match_rows,
            &mut counter_rows,
            &mut conflict_rows,
        );
        request_rows.push(result);
    }

    let mut nonce_rows = Vec::new();
    let mut nonce_ids: Vec<String> = ds.nonces.keys().cloned().collect();
    nonce_ids.sort();
    for nid in nonce_ids {
        let n = &ds.nonces[&nid];
        let init_c = &n.initially_consumed_by_request_id_or_null;
        let final_c = nonce_consumed[&nid].clone();
        nonce_rows.push(NonceRow {
            nonce_id: nid,
            device_id: n.device_id.clone(),
            issued_at: n.issued_at,
            expires_at: n.expires_at,
            initial_status: if init_c.is_some() {
                "consumed".into()
            } else {
                "available".into()
            },
            final_status: if final_c.is_some() {
                "consumed".into()
            } else {
                "available".into()
            },
            consumed_by_request_id_or_null: final_c,
        });
    }

    request_rows.sort_by(|a, b| a.request_id.cmp(&b.request_id));
    quote_rows.sort_by(|a, b| a.request_id.cmp(&b.request_id));
    event_rows.sort_by(|a, b| {
        (a.request_id.as_str(), a.event_seq).cmp(&(b.request_id.as_str(), b.event_seq))
    });
    pcr_rows.sort_by(|a, b| {
        (a.request_id.as_str(), a.pcr_index).cmp(&(b.request_id.as_str(), b.pcr_index))
    });
    reference_match_rows.sort_by(|a, b| {
        (a.request_id.as_str(), a.rule_id.as_str())
            .cmp(&(b.request_id.as_str(), b.rule_id.as_str()))
    });
    counter_rows.sort_by(|a, b| a.request_id.cmp(&b.request_id));
    conflict_rows.sort_by(|a, b| {
        (
            a.request_id.as_str(),
            a.conflict_type.as_str(),
            a.subject.as_str(),
            a.reason_code.as_str(),
        )
            .cmp(&(
                b.request_id.as_str(),
                b.conflict_type.as_str(),
                b.subject.as_str(),
                b.reason_code.as_str(),
            ))
    });

    let summary = Summary {
        request_count: request_rows.len() as u32,
        accepted_request_count: request_rows
            .iter()
            .filter(|r| r.status == "accepted")
            .count() as u32,
        rejected_request_count: request_rows
            .iter()
            .filter(|r| r.status == "rejected")
            .count() as u32,
        quote_row_count: quote_rows.len() as u32,
        event_row_count: event_rows.len() as u32,
        pcr_row_count: pcr_rows.len() as u32,
        reference_match_row_count: reference_match_rows.len() as u32,
        matched_rule_count: request_rows.iter().map(|r| r.matched_rule_count).sum(),
        failed_rule_count: request_rows.iter().map(|r| r.failed_rule_count).sum(),
        initially_consumed_nonce_count: nonce_rows
            .iter()
            .filter(|r| r.initial_status == "consumed")
            .count() as u32,
        finally_consumed_nonce_count: nonce_rows
            .iter()
            .filter(|r| r.final_status == "consumed")
            .count() as u32,
        counter_commit_count: counter_rows.iter().filter(|r| r.committed).count() as u32,
        conflict_count: conflict_rows.len() as u32,
    };

    Report {
        request_rows,
        quote_rows,
        event_rows,
        pcr_rows,
        reference_match_rows,
        counter_rows,
        nonce_rows,
        conflict_rows,
        summary,
    }
}

pub fn verify_data_dir(data_dir: &Path) -> Result<Report, String> {
    let ds = load_dataset(data_dir)?;
    Ok(verify_dataset(ds))
}
