use std::collections::BTreeMap;

use crate::config::Config;
use crate::corpus::Kind;
use crate::db::schema::connect;
use crate::emit::tzif::{serialize, sha256_hex};
use crate::timeline::Zone;
use crate::Result;

/// Replaces the index in one transaction, so a rebuild on an unchanged corpus
/// converges instead of accumulating rows.
pub async fn load(cfg: &Config, zones: &BTreeMap<String, Zone>) -> Result<()> {
    let mut client = connect(cfg).await?;
    let tx = client.transaction().await?;

    tx.batch_execute(
        "DELETE FROM segments; DELETE FROM transitions; \
         DELETE FROM ordinances; DELETE FROM zones;").await?;

    for (name, zone) in zones {
        let raw = serialize(zone);
        let first = zone.transitions.first().map(|t| t.ut).unwrap_or(0);
        let last = zone.transitions.last().map(|t| t.ut).unwrap_or(0);
        tx.execute(
            "INSERT INTO zones (zone, meridian_seconds, tzif_sha256, transition_count, \
             first_transition, last_transition, posix_footer) VALUES ($1,$2,$3,$4,$5,$6,$7)",
            &[name, &zone.meridian, &sha256_hex(&raw),
              &(zone.transitions.len() as i32), &first, &last, &zone.footer],
        ).await?;

        for o in &zone.ordinances {
            let kind = if o.kind == Kind::Establish { "establish" } else { "repeal" };
            tx.execute(
                "INSERT INTO ordinances (zone, ordinance, kind, enacted, enactment_seq, \
                 effective_epoch, effective_anchor, standard_offset, basis, repeals) \
                 VALUES ($1,$2,$3,$4::text::date,$5,$6,$7,$8,$9,$10)",
                &[name, &o.oid, &kind, &o.enacted_text, &(o.enactment_seq as i32),
                  &o.effective_epoch, &o.effective_anchor.as_str(),
                  &o.standard_offset, &o.basis, &o.repeals],
            ).await?;
        }

        let before = zone.offsets_before();
        for (tr, prev) in zone.transitions.iter().zip(before) {
            tx.execute(
                "INSERT INTO transitions (zone, at_epoch, utoff_before, utoff_after, \
                 isdst_after, abbrev_after, ordinance) VALUES ($1,$2,$3,$4,$5,$6,$7)",
                &[name, &tr.ut, &prev, &tr.utoff, &(tr.isdst as i16),
                  &tr.abbrev, &tr.ordinance],
            ).await?;
        }

        for seg in &zone.segments {
            match seg.end {
                Some(end) => {
                    tx.execute(
                        "INSERT INTO segments (zone, valid, ordinance, standard_offset) \
                         VALUES ($1, tstzrange(to_timestamp($2::bigint), \
                         to_timestamp($3::bigint), '[)'), $4, $5)",
                        &[name, &seg.start, &end, &seg.ordinance, &seg.stdoff],
                    ).await?;
                }
                None => {
                    tx.execute(
                        "INSERT INTO segments (zone, valid, ordinance, standard_offset) \
                         VALUES ($1, tstzrange(to_timestamp($2::bigint), NULL, '[)'), $3, $4)",
                        &[name, &seg.start, &seg.ordinance, &seg.stdoff],
                    ).await?;
                }
            }
        }
    }

    tx.commit().await?;
    Ok(())
}
