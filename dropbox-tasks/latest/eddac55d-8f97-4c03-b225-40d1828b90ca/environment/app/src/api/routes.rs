use std::collections::HashMap;
use std::sync::Arc;

use axum::extract::{Path, Query, State};
use axum::http::{header, HeaderMap, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::Deserialize;
use serde_json::json;

use crate::api::resolve::resolve_local;
use crate::api::serve::AppState;
use crate::calendar::civil::days_from_civil;
use crate::precedence::governing_at;
use crate::timeline::Zone;

type Ctx = State<Arc<AppState>>;

pub fn router(state: Arc<AppState>) -> Router {
    let app: Router = Router::new()
        .route("/v1/zones", get(zones))
        .route("/v1/at", get(at))
        .route("/v1/transitions", get(transitions))
        .route("/v1/resolve", post(resolve))
        .route("/v1/tzif/:zone", get(tzif))
        .with_state(state);
    app
}

fn bad(msg: &str) -> Response {
    (StatusCode::BAD_REQUEST, Json(json!({"error": msg}))).into_response()
}

fn missing(msg: &str) -> Response {
    (StatusCode::NOT_FOUND, Json(json!({"error": msg}))).into_response()
}

fn governing(zone: &Zone, t: i64) -> Option<String> {
    governing_at(&zone.segments, t).map(|s| s.ordinance.clone())
}

async fn zones(State(st): Ctx) -> Response {
    Json(json!({"zones": st.zones.keys().collect::<Vec<_>>()})).into_response()
}

async fn at(State(st): Ctx, Query(q): Query<HashMap<String, String>>) -> Response {
    let Some(name) = q.get("zone") else { return bad("zone is required") };
    let Some(entry) = st.zones.get(name) else { return missing("unknown zone") };
    let Some(raw) = q.get("epoch") else { return bad("epoch is required") };
    let Ok(epoch) = raw.parse::<i64>() else { return bad("epoch must be an integer") };

    let (utoff, isdst, abbrev) = entry.zone.local_at(epoch);
    Json(json!({
        "zone": name,
        "epoch": epoch,
        "utoff": utoff,
        "isdst": isdst,
        "abbrev": abbrev,
        "ordinance": governing(&entry.zone, epoch),
    })).into_response()
}

async fn transitions(State(st): Ctx, Query(q): Query<HashMap<String, String>>) -> Response {
    let Some(name) = q.get("zone") else { return bad("zone is required") };
    let Some(entry) = st.zones.get(name) else { return missing("unknown zone") };

    let parse = |k: &str, dflt: i64| -> Result<i64, ()> {
        match q.get(k) {
            None => Ok(dflt),
            Some(v) => v.parse::<i64>().map_err(|_| ()),
        }
    };
    let (Ok(from), Ok(to), Ok(limit)) = (parse("from", i64::MIN), parse("to", i64::MAX),
                                         parse("limit", 100)) else {
        return bad("from, to and limit must be integers");
    };
    if !(1..=1000).contains(&limit) {
        return bad("limit out of range");
    }
    let cursor = match q.get("cursor") {
        None => None,
        Some(v) => match v.parse::<i64>() {
            Ok(c) => Some(c),
            Err(_) => return bad("cursor must be an integer"),
        },
    };

    let before = entry.zone.offsets_before();
    let mut items = Vec::new();
    let mut last_epoch = None;
    let mut next_cursor = None;
    for (tr, prev) in entry.zone.transitions.iter().zip(before) {
        if tr.ut < from || tr.ut > to || cursor.map(|c| tr.ut <= c).unwrap_or(false) {
            continue;
        }
        if items.len() as i64 == limit {
            next_cursor = last_epoch;
            break;
        }
        items.push(json!({
            "at_epoch": tr.ut,
            "utoff_before": prev,
            "utoff_after": tr.utoff,
            "isdst_after": tr.isdst,
            "abbrev_after": tr.abbrev,
            "ordinance": tr.ordinance,
        }));
        last_epoch = Some(tr.ut);
    }
    Json(json!({"items": items, "next_cursor": next_cursor})).into_response()
}

#[derive(Deserialize)]
struct ResolveBody {
    zone: String,
    local: String,
    #[serde(default = "default_policy")]
    policy: String,
    #[serde(default)]
    fold: u8,
}

fn default_policy() -> String {
    "reject".to_string()
}

fn parse_local(text: &str) -> Option<i64> {
    let (date, time) = text.split_once('T')?;
    let d: Vec<&str> = date.split('-').collect();
    let t: Vec<&str> = time.split(':').collect();
    if d.len() != 3 || t.len() != 3 {
        return None;
    }
    let days = days_from_civil(d[0].parse().ok()?, d[1].parse().ok()?, d[2].parse().ok()?);
    let secs = t[0].parse::<i64>().ok()? * 3600
        + t[1].parse::<i64>().ok()? * 60
        + t[2].parse::<i64>().ok()?;
    Some(days * 86400 + secs)
}

async fn resolve(State(st): Ctx, Json(body): Json<ResolveBody>) -> Response {
    let Some(entry) = st.zones.get(&body.zone) else { return missing("unknown zone") };
    if body.policy != "reject" && body.policy != "shift" {
        return bad("policy must be reject or shift");
    }
    if body.fold > 1 {
        return bad("fold must be 0 or 1");
    }
    let Some(local) = parse_local(&body.local) else { return bad("local must be YYYY-MM-DDTHH:MM:SS") };

    match resolve_local(&entry.zone, local, &body.policy, body.fold) {
        None => (StatusCode::CONFLICT,
                 Json(json!({"error": "local time does not exist", "kind": "gap"}))).into_response(),
        Some((epoch, kind)) => {
            let (utoff, isdst, abbrev) = entry.zone.local_at(epoch);
            Json(json!({
                "zone": body.zone,
                "epoch": epoch,
                "kind": kind.as_str(),
                "utoff": utoff,
                "isdst": isdst,
                "abbrev": abbrev,
            })).into_response()
        }
    }
}

async fn tzif(State(st): Ctx, Path(name): Path<String>, headers: HeaderMap) -> Response {
    let Some(entry) = st.zones.get(&name) else { return missing("unknown zone") };
    let etag = format!("\"{}\"", entry.sha);
    if let Some(inm) = headers.get(header::IF_NONE_MATCH).and_then(|v| v.to_str().ok()) {
        if inm == etag {
            return (StatusCode::NOT_MODIFIED, [(header::ETAG, etag)]).into_response();
        }
    }
    (
        StatusCode::OK,
        [(header::ETAG, etag),
         (header::CONTENT_TYPE, "application/octet-stream".to_string())],
        entry.bytes.clone(),
    ).into_response()
}
