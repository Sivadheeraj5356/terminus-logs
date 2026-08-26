#!/bin/bash
set -euo pipefail

cd /app

cat > /app/reconcile.js <<'JS'
#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const dbPath = "/app/contracts/fare_policy.sqlite";
const outputDir = "/app/output";

function listFiles(dir, suffix) {
  return fs.readdirSync(dir)
    .filter((name) => name.endsWith(suffix))
    .sort()
    .map((name) => path.join(dir, name));
}

function readJsonlDir(dir) {
  const rows = [];
  for (const file of listFiles(dir, ".jsonl")) {
    const text = fs.readFileSync(file, "utf8").trim();
    if (!text) continue;
    for (const line of text.split(/\n/)) {
      rows.push(JSON.parse(line));
    }
  }
  return rows;
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field);
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      field = "";
    } else if (char !== "\r") {
      field += char;
    }
  }
  row.push(field);
  if (row.some((value) => value !== "")) rows.push(row);

  const headers = rows.shift();
  return rows.map((values) => {
    const row = {};
    headers.forEach((header, index) => {
      row[header] = values[index];
    });
    return row;
  });
}

function readCsvDir(dir) {
  return listFiles(dir, ".csv").flatMap((file) => parseCsv(fs.readFileSync(file, "utf8")));
}

function csvCell(value) {
  const text = String(value);
  if (!/[",\r\n]/.test(text)) return text;
  return `"${text.replace(/"/g, '""')}"`;
}

function writeCsv(file, header, rows) {
  const text = [
    header.join(","),
    ...rows.map((row) => header.map((name) => csvCell(row[name])).join(","))
  ].join("\n") + "\n";
  fs.writeFileSync(file, text);
}

function approvedOverridesByTap(rows) {
  const overrides = new Map();
  for (const row of rows) {
    if (String(row.approved).trim().toLowerCase() !== "true") continue;
    if (!overrides.has(row.tap_id)) overrides.set(row.tap_id, new Map());
    const byAction = overrides.get(row.tap_id);
    const current = byAction.get(row.action);
    if (!current || row.override_id > current.override_id) {
      byAction.set(row.action, row);
    }
  }
  return overrides;
}

function approvedZoneAdjustmentsByKey(rows) {
  const adjustments = new Map();
  for (const row of rows) {
    if (String(row.approved).trim().toLowerCase() !== "true") continue;
    const key = `${row.service_date}\t${row.route_id}\t${row.station_id}`;
    if (!adjustments.has(key)) adjustments.set(key, []);
    adjustments.get(key).push(row);
  }
  return adjustments;
}

function effectiveServiceZone(adjustments, tap, route) {
  const key = `${tap.service_date}\t${tap.route_id}\t${tap.station_id}`;
  const matches = (adjustments.get(key) || [])
    .filter((row) => row.direction === tap.direction || row.direction === "all")
    .sort((a, b) => {
      const aExact = a.direction === tap.direction ? 1 : 0;
      const bExact = b.direction === tap.direction ? 1 : 0;
      return (aExact - bExact) || a.zone_adjustment_id.localeCompare(b.zone_adjustment_id);
    });
  return matches.length === 0 ? route.service_zone : matches.at(-1).service_zone;
}

function approvedCorrectionsByTap(rows) {
  const supportedFields = new Set(["rider_id", "route_id", "station_id", "device_status", "tapped_at", "service_date"]);
  const corrections = new Map();
  for (const row of rows) {
    if (row.approved !== true || !supportedFields.has(row.field)) continue;
    if (!corrections.has(row.tap_id)) corrections.set(row.tap_id, new Map());
    const byField = corrections.get(row.tap_id);
    const current = byField.get(row.field);
    if (!current || row.correction_id > current.correction_id) {
      byField.set(row.field, row);
    }
  }
  return corrections;
}

function applyTapCorrections(taps, corrections) {
  const correctedTapIds = new Set();
  const correctedTaps = taps.map((tap) => {
    const updated = { ...tap };
    updated._original = { ...tap };
    const tapCorrections = corrections.get(tap.tap_id);
    let serviceDateCorrection = null;
    if (tapCorrections) {
      for (const [field, correction] of tapCorrections.entries()) {
        if (field === "service_date") {
          serviceDateCorrection = correction;
          continue;
        }
        if (updated[field] !== correction.value) {
          updated[field] = correction.value;
          correctedTapIds.add(tap.tap_id);
        }
      }
    }
    updated.service_date = normalizedServiceDate(updated.tapped_at);
    if (serviceDateCorrection && updated.service_date !== serviceDateCorrection.value) {
      updated.service_date = serviceDateCorrection.value;
      correctedTapIds.add(tap.tap_id);
    }
    return updated;
  });
  return { correctedTaps, correctedTapIds };
}

function normalizedServiceDate(tappedAt) {
  const [datePart, timePart] = tappedAt.split("T");
  if (timePart.slice(0, 8) >= "03:00:00") return datePart;
  const noonUtc = new Date(`${datePart}T12:00:00Z`);
  noonUtc.setUTCDate(noonUtc.getUTCDate() - 1);
  return noonUtc.toISOString().slice(0, 10);
}

function approvedExceptionsByTap(rows) {
  const exceptions = new Map();
  for (const row of rows) {
    if (row.approved !== true) continue;
    if (!exceptions.has(row.tap_id)) exceptions.set(row.tap_id, []);
    exceptions.get(row.tap_id).push(row);
  }
  for (const tapExceptions of exceptions.values()) {
    tapExceptions.sort((a, b) => a.exception_id.localeCompare(b.exception_id));
  }
  return exceptions;
}

function applyExceptionCredits(exceptions, baseCharge, expressCents) {
  let exceptionCredit = 0;
  for (const exception of exceptions) {
    let remaining = Number(exception.amount_cents);
    if (exception.scope === "base" || exception.scope === "both") {
      const reduction = Math.min(baseCharge, remaining);
      baseCharge -= reduction;
      exceptionCredit += reduction;
      remaining -= reduction;
    }
    if (remaining > 0 && (exception.scope === "surcharge" || exception.scope === "both")) {
      const reduction = Math.min(expressCents, remaining);
      expressCents -= reduction;
      exceptionCredit += reduction;
    }
  }
  return { baseCharge, expressCents, exceptionCredit };
}

function sqliteRows(sql) {
  const out = execFileSync("sqlite3", ["-json", dbPath, sql], { encoding: "utf8" }).trim();
  return out ? JSON.parse(out) : [];
}

function indexBy(rows, key) {
  const map = new Map();
  for (const row of rows) map.set(row[key], row);
  return map;
}

function dayKey(serviceDate, riderId) {
  return `${serviceDate}\t${riderId}`;
}

function getDay(days, serviceDate, riderId) {
  const key = dayKey(serviceDate, riderId);
  if (!days.has(key)) {
    days.set(key, {
      service_date: serviceDate,
      rider_id: riderId,
      baseCharges: [],
      express_cents: 0,
      tap_count: 0,
      distinctRoutes: new Set(),
      zones: new Set(),
      pass_credit_cents: 0,
      disruption_credit_cents: 0,
      subsidy_credit_cents: 0,
      exception_credit_cents: 0,
      hold_credit_cents: 0,
      carryover_credit_cents: 0,
      account_cap_credit_cents: 0,
      account_credit_cents: 0,
      adjustment_cents: 0,
      unresolved_count: 0,
      lastFareable: null,
      rider_type: null,
      routeFamilies: new Map()
    });
  }
  return days.get(key);
}

function getRouteFamily(day, routeFamily) {
  if (!day.routeFamilies.has(routeFamily)) {
    day.routeFamilies.set(routeFamily, {
      service_date: day.service_date,
      rider_id: day.rider_id,
      route_family: routeFamily,
      preCapBaseCents: 0,
      capExcludedBaseCents: 0,
      capEligibleBaseCents: 0,
      capEligibleBaseAfterDailyCapCents: 0,
      baseAfterDailyCapCents: 0,
      expressChargedCents: 0,
      capCreditCents: 0,
      accountCapCreditCents: 0,
      accountCreditCents: 0,
      tapCount: 0,
      zones: new Set()
    });
  }
  return day.routeFamilies.get(routeFamily);
}

function allocateCapCredit(routeFamilies, capCredit) {
  const allocations = new Map(routeFamilies.map((row) => [row.route_family, 0]));
  if (capCredit <= 0) return allocations;

  const totalBase = routeFamilies.reduce((sum, row) => sum + row.capEligibleBaseCents, 0);
  if (totalBase <= 0) return allocations;

  const remainders = [];
  let allocated = 0;
  for (const row of routeFamilies) {
    const rawShare = capCredit * row.capEligibleBaseCents;
    const share = Math.floor(rawShare / totalBase);
    allocations.set(row.route_family, share);
    allocated += share;
    remainders.push({ route_family: row.route_family, remainder: rawShare % totalBase });
  }

  const leftover = capCredit - allocated;
  remainders
    .sort((a, b) => (b.remainder - a.remainder) || a.route_family.localeCompare(b.route_family))
    .slice(0, leftover)
    .forEach((row) => allocations.set(row.route_family, allocations.get(row.route_family) + 1));

  return allocations;
}

function activeAccountLink(accountLinks, riderId, serviceDate) {
  const matches = accountLinks
    .filter((link) => (
      link.rider_id === riderId &&
      link.status === "active" &&
      link.active_from <= serviceDate &&
      serviceDate <= link.active_to
    ))
    .sort((a, b) => a.account_id.localeCompare(b.account_id));
  return matches.at(-1) || null;
}

function allocateAccountCapCredit(families, capCredit) {
  const allocations = new Map(families.map((row) => [`${row.day.rider_id}\t${row.family.route_family}`, 0]));
  if (capCredit <= 0) return allocations;

  const totalBase = families.reduce((sum, row) => sum + row.family.capEligibleBaseAfterDailyCapCents, 0);
  if (totalBase <= 0) return allocations;

  const remainders = [];
  let allocated = 0;
  for (const row of families) {
    const key = `${row.day.rider_id}\t${row.family.route_family}`;
    const rawShare = capCredit * row.family.capEligibleBaseAfterDailyCapCents;
    const share = Math.floor(rawShare / totalBase);
    allocations.set(key, share);
    allocated += share;
    remainders.push({
      key,
      rider_id: row.day.rider_id,
      route_family: row.family.route_family,
      remainder: rawShare % totalBase
    });
  }

  const leftover = capCredit - allocated;
  remainders
    .sort((a, b) => (b.remainder - a.remainder) || a.rider_id.localeCompare(b.rider_id) || a.route_family.localeCompare(b.route_family))
    .slice(0, leftover)
    .forEach((row) => allocations.set(row.key, allocations.get(row.key) + 1));

  return allocations;
}

function applyAccountCaps(sortedDays, accountLinks, accountCaps) {
  const groups = new Map();
  for (const day of sortedDays) {
    if (day.tap_count <= 0) continue;
    const link = activeAccountLink(accountLinks, day.rider_id, day.service_date);
    if (!link) continue;
    const key = `${day.service_date}\t${link.account_id}`;
    if (!groups.has(key)) {
      groups.set(key, {
        service_date: day.service_date,
        account_id: link.account_id,
        days: [],
        zones: new Set()
      });
    }
    const group = groups.get(key);
    group.days.push(day);
    for (const zone of day.zones) group.zones.add(zone);
  }

  const accountRows = [];
  for (const group of [...groups.values()].sort((a, b) => a.service_date.localeCompare(b.service_date) || a.account_id.localeCompare(b.account_id))) {
    const applicableCaps = accountCaps
      .filter((cap) => cap.account_id === group.account_id && group.zones.has(cap.service_zone))
      .sort((a, b) => (Number(a.cap_cents) - Number(b.cap_cents)) || a.service_zone.localeCompare(b.service_zone));
    if (applicableCaps.length === 0) continue;
    const selectedCap = applicableCaps.at(-1);
    const families = [];
    for (const day of group.days.sort((a, b) => a.rider_id.localeCompare(b.rider_id))) {
      for (const family of [...day.routeFamilies.values()].sort((a, b) => a.route_family.localeCompare(b.route_family))) {
        if (family.capEligibleBaseAfterDailyCapCents > 0) {
          families.push({ day, family });
        }
      }
    }
    const baseBeforeAccountCap = families.reduce((sum, row) => sum + row.family.capEligibleBaseAfterDailyCapCents, 0);
    const accountCap = Number(selectedCap.cap_cents);
    if (baseBeforeAccountCap <= accountCap) continue;
    const accountCapCredit = baseBeforeAccountCap - accountCap;
    const allocations = allocateAccountCapCredit(families, accountCapCredit);
    for (const row of families) {
      const key = `${row.day.rider_id}\t${row.family.route_family}`;
      const allocated = allocations.get(key) || 0;
      row.family.capEligibleBaseAfterDailyCapCents -= allocated;
      row.family.baseAfterDailyCapCents -= allocated;
      row.family.accountCapCreditCents += allocated;
      row.day.account_cap_credit_cents += allocated;
    }
    accountRows.push({
      service_date: group.service_date,
      account_id: group.account_id,
      service_zone: selectedCap.service_zone,
      base_before_account_cap_cents: baseBeforeAccountCap,
      account_cap_cents: accountCap,
      account_cap_credit_cents: accountCapCredit,
      participating_rider_days: group.days.length
    });
  }
  return accountRows;
}

function approvedAccountCredits(rows, reversals) {
  const credits = new Map();
  for (const row of rows) {
    if (row.approved !== true) continue;
    const dailyLimit = unrestrictedFilter(row.daily_limit_cents) ? null : Number(row.daily_limit_cents);
    const reversedCents = reversals.get(`account_credit\t${row.account_id}\t${row.credit_id}`) || 0;
    if (!credits.has(row.account_id)) credits.set(row.account_id, []);
    credits.get(row.account_id).push({
      ...row,
      daily_limit_cents: dailyLimit,
      remaining_cents: Math.max(0, Number(row.amount_cents) - reversedCents)
    });
  }
  for (const accountCredits of credits.values()) {
    accountCredits.sort((a, b) => (
      a.earned_service_date.localeCompare(b.earned_service_date) ||
      a.credit_id.localeCompare(b.credit_id)
    ));
  }
  return credits;
}

function allocateAccountStageCredit(families, amount, amountKey) {
  const allocations = new Map(families.map((row) => [`${row.day.rider_id}\t${row.family.route_family}`, 0]));
  if (amount <= 0) return allocations;

  const total = families.reduce((sum, row) => sum + row.family[amountKey], 0);
  if (total <= 0) return allocations;

  const credit = Math.min(amount, total);
  const remainders = [];
  let allocated = 0;
  for (const row of families) {
    const key = `${row.day.rider_id}\t${row.family.route_family}`;
    const rawShare = credit * row.family[amountKey];
    const share = Math.floor(rawShare / total);
    allocations.set(key, share);
    allocated += share;
    remainders.push({
      key,
      rider_id: row.day.rider_id,
      route_family: row.family.route_family,
      remainder: rawShare % total
    });
  }

  const leftover = credit - allocated;
  remainders
    .sort((a, b) => (b.remainder - a.remainder) || a.rider_id.localeCompare(b.rider_id) || a.route_family.localeCompare(b.route_family))
    .slice(0, leftover)
    .forEach((row) => allocations.set(row.key, allocations.get(row.key) + 1));
  return allocations;
}

function unrestrictedFilter(value) {
  return value === undefined || value === null || value === "" || value === "all";
}

function accountCreditMatches(credit, day, family) {
  if (!unrestrictedFilter(credit.rider_id) && credit.rider_id !== day.rider_id) {
    return false;
  }
  if (!unrestrictedFilter(credit.route_family) && credit.route_family !== family.route_family) {
    return false;
  }
  if (!unrestrictedFilter(credit.service_zone) && !family.zones.has(credit.service_zone)) {
    return false;
  }
  return true;
}

function accountCreditFamilies(days, amountKey, credit) {
  const families = [];
  for (const day of days.sort((a, b) => a.rider_id.localeCompare(b.rider_id))) {
    for (const family of [...day.routeFamilies.values()].sort((a, b) => a.route_family.localeCompare(b.route_family))) {
      if (family[amountKey] > 0 && accountCreditMatches(credit, day, family)) {
        families.push({ day, family });
      }
    }
  }
  return families;
}

function reduceAccountCreditStage(days, credit, amountKey, dateRemainingCents) {
  const families = accountCreditFamilies(days, amountKey, credit);
  const available = families.reduce((sum, row) => sum + row.family[amountKey], 0);
  const reduction = Math.min(credit.remaining_cents, dateRemainingCents, available);
  if (reduction <= 0) return 0;

  const allocations = allocateAccountStageCredit(families, reduction, amountKey);
  let applied = 0;
  for (const row of families) {
    const key = `${row.day.rider_id}\t${row.family.route_family}`;
    const allocated = allocations.get(key) || 0;
    row.family[amountKey] -= allocated;
    row.family.accountCreditCents += allocated;
    row.day.account_credit_cents += allocated;
    applied += allocated;
  }
  credit.remaining_cents -= applied;
  return applied;
}

function applyAccountCredits(sortedDays, accountLinks, accountCredits) {
  const groups = new Map();
  for (const day of sortedDays) {
    if (day.tap_count <= 0) continue;
    const link = activeAccountLink(accountLinks, day.rider_id, day.service_date);
    if (!link) continue;
    const key = `${day.service_date}\t${link.account_id}`;
    if (!groups.has(key)) {
      groups.set(key, {
        service_date: day.service_date,
        account_id: link.account_id,
        days: []
      });
    }
    groups.get(key).days.push(day);
  }

  for (const group of [...groups.values()].sort((a, b) => a.service_date.localeCompare(b.service_date) || a.account_id.localeCompare(b.account_id))) {
    const credits = accountCredits.get(group.account_id) || [];
    for (const credit of credits) {
      if (credit.remaining_cents <= 0) continue;
      if (!(credit.earned_service_date < group.service_date && group.service_date <= credit.expires_service_date)) {
        continue;
      }
      let dateRemainingCents = credit.daily_limit_cents === null
        ? credit.remaining_cents
        : Math.min(credit.remaining_cents, credit.daily_limit_cents);
      if (dateRemainingCents <= 0) continue;
      if (credit.scope === "base" || credit.scope === "both") {
        const applied = reduceAccountCreditStage(group.days, credit, "baseAfterDailyCapCents", dateRemainingCents);
        dateRemainingCents -= applied;
      }
      if (credit.remaining_cents > 0 && dateRemainingCents > 0 && (credit.scope === "surcharge" || credit.scope === "both")) {
        reduceAccountCreditStage(group.days, credit, "expressChargedCents", dateRemainingCents);
      }
    }
  }
}

function tapAuditRow(tap, values = {}) {
  const original = tap._original;
  return {
    tap_id: tap.tap_id,
    service_date: tap.service_date,
    original_tapped_at: original.tapped_at,
    tapped_at: tap.tapped_at,
    original_rider_id: original.rider_id,
    rider_id: tap.rider_id,
    original_route_id: original.route_id,
    route_id: tap.route_id,
    original_station_id: original.station_id,
    station_id: tap.station_id,
    original_device_status: original.device_status,
    device_status: tap.device_status,
    unresolved_reason: values.unresolved_reason || "",
    route_family: values.route_family || "",
    base_after_discount_cents: values.base_after_discount_cents || 0,
    transfer_credit_cents: values.transfer_credit_cents || 0,
    pass_credit_cents: values.pass_credit_cents || 0,
    disruption_credit_cents: values.disruption_credit_cents || 0,
    subsidy_credit_cents: values.subsidy_credit_cents || 0,
    exception_credit_cents: values.exception_credit_cents || 0,
    base_before_cap_cents: values.base_before_cap_cents || 0,
    express_before_cap_cents: values.express_before_cap_cents || 0
  };
}

function activePassCovers(passes, riderId, serviceDate, serviceZone) {
  return passes.some((pass) => (
    pass.rider_id === riderId &&
    pass.status === "active" &&
    pass.active_from <= serviceDate &&
    serviceDate <= pass.active_to &&
    (pass.service_zone === serviceZone || pass.service_zone === "all")
  ));
}

function matchingSubsidy(subsidies, riderId, serviceDate, serviceZone) {
  return subsidies
    .filter((subsidy) => (
      subsidy.rider_id === riderId &&
      subsidy.status === "active" &&
      subsidy.active_from <= serviceDate &&
      serviceDate <= subsidy.active_to &&
      (subsidy.service_zone === serviceZone || subsidy.service_zone === "all")
    ))
    .sort((a, b) => a.subsidy_id.localeCompare(b.subsidy_id))
    .at(-1);
}

function subsidyMonthKey(subsidy, serviceDate) {
  return `${subsidy.rider_id}\t${subsidy.subsidy_id}\t${serviceDate.slice(0, 7)}`;
}

function subsidyRecoveryUsage(rows) {
  const usage = new Map();
  for (const row of rows) {
    if (row.approved !== true) continue;
    const key = `${row.rider_id}\t${row.subsidy_id}\t${row.service_month}`;
    usage.set(key, (usage.get(key) || 0) + Number(row.amount_cents));
  }
  return usage;
}

function creditReversalUsage(rows) {
  const usage = new Map();
  for (const row of rows) {
    if (row.approved !== true) continue;
    let key = null;
    if (row.target_kind === "carryover") {
      key = `carryover\t${row.rider_id}\t${row.carryover_id}`;
    } else if (row.target_kind === "account_credit") {
      key = `account_credit\t${row.account_id}\t${row.credit_id}`;
    }
    if (!key) continue;
    usage.set(key, (usage.get(key) || 0) + Number(row.amount_cents));
  }
  return usage;
}

function approvedHoldsByFamily(rows) {
  const holds = new Map();
  for (const row of rows) {
    if (row.approved !== true) continue;
    const key = `${row.service_date}\t${row.rider_id}\t${row.route_family}`;
    if (!holds.has(key)) holds.set(key, []);
    holds.get(key).push(row);
  }
  for (const familyHolds of holds.values()) {
    familyHolds.sort((a, b) => a.hold_id.localeCompare(b.hold_id));
  }
  return holds;
}

function applySettlementHolds(day, holds) {
  for (const family of day.routeFamilies.values()) {
    const key = `${day.service_date}\t${day.rider_id}\t${family.route_family}`;
    const familyHolds = holds.get(key) || [];
    for (const hold of familyHolds) {
      let remaining = Number(hold.amount_cents);
      let holdCredit = 0;
      if (hold.scope === "base" || hold.scope === "both") {
        const reduction = Math.min(family.preCapBaseCents, remaining);
        family.preCapBaseCents -= reduction;
        remaining -= reduction;
        holdCredit += reduction;
      }
      if (remaining > 0 && (hold.scope === "surcharge" || hold.scope === "both")) {
        const reduction = Math.min(family.expressChargedCents, remaining);
        family.expressChargedCents -= reduction;
        holdCredit += reduction;
      }
      day.hold_credit_cents += holdCredit;
    }
  }
}

function approvedCarryoversByRider(rows, reversals) {
  const carryovers = new Map();
  for (const row of rows) {
    if (row.approved !== true) continue;
    const dailyLimit = unrestrictedFilter(row.daily_limit_cents) ? null : Number(row.daily_limit_cents);
    const reversedCents = reversals.get(`carryover\t${row.rider_id}\t${row.carryover_id}`) || 0;
    if (!carryovers.has(row.rider_id)) carryovers.set(row.rider_id, []);
    carryovers.get(row.rider_id).push({
      ...row,
      daily_limit_cents: dailyLimit,
      remaining_cents: Math.max(0, Number(row.amount_cents) - reversedCents)
    });
  }
  for (const riderCarryovers of carryovers.values()) {
    riderCarryovers.sort((a, b) => (
      a.earned_service_date.localeCompare(b.earned_service_date) ||
      a.carryover_id.localeCompare(b.carryover_id)
    ));
  }
  return carryovers;
}

function allocateCarryoverStage(families, amount, amountKey) {
  const allocations = new Map(families.map((family) => [family.route_family, 0]));
  const total = families.reduce((sum, family) => sum + family[amountKey], 0);
  const credit = Math.min(amount, total);
  if (credit <= 0) return allocations;

  const remainders = [];
  let allocated = 0;
  for (const family of families) {
    const rawShare = credit * family[amountKey];
    const share = Math.floor(rawShare / total);
    allocations.set(family.route_family, share);
    allocated += share;
    remainders.push({ route_family: family.route_family, remainder: rawShare % total });
  }

  const leftover = credit - allocated;
  remainders
    .sort((a, b) => (b.remainder - a.remainder) || a.route_family.localeCompare(b.route_family))
    .slice(0, leftover)
    .forEach((row) => allocations.set(row.route_family, allocations.get(row.route_family) + 1));
  return allocations;
}

function matchingCarryoverFamilies(day, carryover, amountKey) {
  const families = carryover.route_family === "all"
    ? [...day.routeFamilies.values()]
    : (day.routeFamilies.has(carryover.route_family) ? [day.routeFamilies.get(carryover.route_family)] : []);
  return families
    .filter((family) => family[amountKey] > 0)
    .sort((a, b) => a.route_family.localeCompare(b.route_family));
}

function reduceCarryoverStage(day, carryover, amountKey, dateRemainingCents) {
  const families = matchingCarryoverFamilies(day, carryover, amountKey);
  if (families.length === 0) return 0;

  const available = families.reduce((sum, family) => sum + family[amountKey], 0);
  const reduction = Math.min(carryover.remaining_cents, dateRemainingCents, available);
  if (reduction <= 0) return 0;

  const allocations = carryover.route_family === "all"
    ? allocateCarryoverStage(families, reduction, amountKey)
    : new Map([[families[0].route_family, reduction]]);
  let applied = 0;
  for (const family of families) {
    const allocated = allocations.get(family.route_family) || 0;
    family[amountKey] -= allocated;
    applied += allocated;
  }
  carryover.remaining_cents -= applied;
  day.carryover_credit_cents += applied;
  return applied;
}

function applyCarryoverCredits(sortedDays, carryovers) {
  for (const day of sortedDays) {
    const riderCarryovers = carryovers.get(day.rider_id) || [];
    for (const carryover of riderCarryovers) {
      if (carryover.remaining_cents <= 0) continue;
      if (!(carryover.earned_service_date < day.service_date && day.service_date <= carryover.expires_service_date)) {
        continue;
      }

      let dateRemainingCents = carryover.daily_limit_cents === null
        ? carryover.remaining_cents
        : Math.min(carryover.remaining_cents, carryover.daily_limit_cents);
      if (dateRemainingCents <= 0) continue;

      if (carryover.scope === "base" || carryover.scope === "both") {
        const applied = reduceCarryoverStage(day, carryover, "preCapBaseCents", dateRemainingCents);
        dateRemainingCents -= applied;
      }
      if (carryover.remaining_cents > 0 && dateRemainingCents > 0 && (carryover.scope === "surcharge" || carryover.scope === "both")) {
        reduceCarryoverStage(day, carryover, "expressChargedCents", dateRemainingCents);
      }
    }
  }
}

function approvedMinimumsByFamily(rows) {
  const minimums = new Map();
  for (const row of rows) {
    if (row.status !== "active") continue;
    const key = `${row.service_date}\t${row.rider_id}\t${row.route_family}`;
    const current = minimums.get(key);
    if (!current || row.minimum_id > current.minimum_id) {
      minimums.set(key, row);
    }
  }
  return minimums;
}

function applyFamilyMinimums(sortedDays, minimums) {
  for (const day of sortedDays) {
    for (const family of day.routeFamilies.values()) {
      const key = `${day.service_date}\t${day.rider_id}\t${family.route_family}`;
      const minimum = minimums.get(key);
      if (!minimum) continue;

      const minBase = Number(minimum.min_base_cents);
      if (family.preCapBaseCents < minBase) {
        family.preCapBaseCents = minBase;
      }

      const minExpress = Number(minimum.min_express_cents);
      if (family.expressChargedCents < minExpress) {
        family.expressChargedCents = minExpress;
      }
    }
  }
}

function approvedCapExclusionsByFamily(rows) {
  const exclusions = new Map();
  for (const row of rows) {
    if (row.approved !== true) continue;
    const key = `${row.service_date}\t${row.rider_id}\t${row.route_family}`;
    if (!exclusions.has(key)) exclusions.set(key, []);
    exclusions.get(key).push(row);
  }
  for (const familyExclusions of exclusions.values()) {
    familyExclusions.sort((a, b) => a.exclusion_id.localeCompare(b.exclusion_id));
  }
  return exclusions;
}

function applyCapExclusions(sortedDays, capExclusions) {
  for (const day of sortedDays) {
    const routeFamilies = [...day.routeFamilies.values()].sort((a, b) => (
      a.route_family.localeCompare(b.route_family)
    ));
    for (const family of routeFamilies) {
      const key = `${day.service_date}\t${day.rider_id}\t${family.route_family}`;
      const exclusions = capExclusions.get(key) || [];
      for (const exclusion of exclusions) {
        const eligibleBase = Math.max(0, family.preCapBaseCents - family.capExcludedBaseCents);
        const excluded = Math.min(eligibleBase, Number(exclusion.amount_cents));
        family.capExcludedBaseCents += excluded;
      }
    }
  }
}

function disruptionCreditForTap(disruptions, tap, route, baseCharge) {
  if (baseCharge <= 0) return 0;
  const tapTime = tap.tapped_at.slice(11, 16);
  const credit = disruptions
    .filter((disruption) => (
      disruption.approved === true &&
      disruption.service_date === tap.service_date &&
      disruption.route_family === route.route_family &&
      disruption.start_time <= tapTime &&
      tapTime < disruption.end_time
    ))
    .reduce((sum, disruption) => sum + Number(disruption.credit_cents), 0);
  return Math.min(baseCharge, credit);
}

function stationPairSurchargeForTap(stationPairSurcharges, previous, tap, route) {
  if (!previous) return null;
  const matches = stationPairSurcharges
    .filter((row) => (
      Number(row.active) === 1 &&
      row.from_station_id === previous.station_id &&
      row.to_station_id === tap.station_id &&
      row.route_family === route.route_family
    ))
    .sort((a, b) => a.surcharge_id.localeCompare(b.surcharge_id));
  if (matches.length === 0) return null;
  return Number(matches.at(-1).amount_cents);
}

function minutesBetween(a, b) {
  return Math.floor((Date.parse(b) - Date.parse(a)) / 60000);
}

function sortedObjectFromCounts(counts) {
  const obj = {};
  for (const key of Object.keys(counts).sort()) {
    obj[key] = counts[key];
  }
  return obj;
}

function main() {
  const riders = indexBy(sqliteRows("SELECT rider_id, rider_type FROM riders"), "rider_id");
  const discounts = indexBy(sqliteRows("SELECT rider_type, discount_percent FROM rider_type_rules"), "rider_type");
  const routes = indexBy(sqliteRows("SELECT route_id, service_zone, route_family, base_cents, express_surcharge_cents, active FROM routes"), "route_id");
  const stations = indexBy(sqliteRows("SELECT station_id, station_zone, active FROM stations"), "station_id");
  const caps = sqliteRows("SELECT rider_type, service_zone, cap_cents FROM daily_caps");
  const accountCaps = sqliteRows("SELECT account_id, service_zone, cap_cents FROM account_daily_caps");
  const transferRows = sqliteRows("SELECT from_family, to_family, minutes FROM transfer_rules");
  const transferRules = new Map(transferRows.map((row) => [`${row.from_family}\t${row.to_family}`, row.minutes]));
  const stationPairSurcharges = sqliteRows("SELECT surcharge_id, from_station_id, to_station_id, route_family, amount_cents, active FROM station_pair_surcharges");

  const corrections = approvedCorrectionsByTap(readJsonlDir("/app/data/corrections"));
  const { correctedTaps, correctedTapIds } = applyTapCorrections(readJsonlDir("/app/data/taps"), corrections);
  const taps = correctedTaps.sort((a, b) => (
    a.service_date.localeCompare(b.service_date) ||
    a.rider_id.localeCompare(b.rider_id) ||
    a.tapped_at.localeCompare(b.tapped_at) ||
    a.tap_id.localeCompare(b.tap_id)
  ));
  const passes = readCsvDir("/app/data/passes");
  const subsidies = readCsvDir("/app/data/subsidies");
  const adjustments = readJsonlDir("/app/data/adjustments");
  const disruptions = readJsonlDir("/app/data/disruptions");
  const exceptions = approvedExceptionsByTap(readJsonlDir("/app/data/exceptions"));
  const holds = approvedHoldsByFamily(readJsonlDir("/app/data/holds"));
  const creditReversals = creditReversalUsage(readJsonlDir("/app/data/credit-reversals"));
  const carryovers = approvedCarryoversByRider(readJsonlDir("/app/data/carryovers"), creditReversals);
  const minimums = approvedMinimumsByFamily(readCsvDir("/app/data/minimums"));
  const capExclusions = approvedCapExclusionsByFamily(readJsonlDir("/app/data/cap-exclusions"));
  const accountLinks = readCsvDir("/app/data/accounts");
  const accountCredits = approvedAccountCredits(readJsonlDir("/app/data/account-credits"), creditReversals);
  const overrides = approvedOverridesByTap(readCsvDir("/app/data/overrides"));
  const zoneAdjustments = approvedZoneAdjustmentsByKey(readCsvDir("/app/data/zone-adjustments"));

  const days = new Map();
  const unresolvedEvents = [];
  const subsidyUsage = subsidyRecoveryUsage(readJsonlDir("/app/data/subsidy-recoveries"));
  const tapAuditRows = [];

  function recordUnresolved(tap, reason) {
    const day = getDay(days, tap.service_date, tap.rider_id);
    day.unresolved_count += 1;
    unresolvedEvents.push({
      tap_id: tap.tap_id,
      rider_id: tap.rider_id,
      service_date: tap.service_date,
      reason
    });
    tapAuditRows.push(tapAuditRow(tap, { unresolved_reason: reason }));
  }

  for (const tap of taps) {
    if (tap.device_status !== "accepted") {
      recordUnresolved(tap, "rejected_device");
      continue;
    }

    const rider = riders.get(tap.rider_id);
    if (!rider) {
      recordUnresolved(tap, "unknown_rider");
      continue;
    }

    const route = routes.get(tap.route_id);
    if (!route || Number(route.active) !== 1) {
      recordUnresolved(tap, "unknown_route");
      continue;
    }

    const station = stations.get(tap.station_id);
    if (!station || Number(station.active) !== 1) {
      recordUnresolved(tap, "inactive_station");
      continue;
    }

    const serviceZone = effectiveServiceZone(zoneAdjustments, tap, route);
    const day = getDay(days, tap.service_date, tap.rider_id);
    day.rider_type = rider.rider_type;
    day.tap_count += 1;
    day.distinctRoutes.add(route.route_id);
    day.zones.add(serviceZone);

    const tapOverrides = overrides.get(tap.tap_id) || new Map();
    const previous = day.lastFareable;
    let baseCents = Number(route.base_cents);
    if (tapOverrides.has("base_override")) {
      baseCents = Number(tapOverrides.get("base_override").amount_cents);
    }
    let expressCents = Number(route.express_surcharge_cents);
    if (tapOverrides.has("surcharge_override")) {
      expressCents = Number(tapOverrides.get("surcharge_override").amount_cents);
    }
    let stationPairSurcharge = stationPairSurchargeForTap(stationPairSurcharges, previous, tap, route);
    if (stationPairSurcharge !== null) {
      if (tapOverrides.has("station_pair_surcharge_override")) {
        stationPairSurcharge = Number(tapOverrides.get("station_pair_surcharge_override").amount_cents);
      }
      expressCents += stationPairSurcharge;
    }

    const discount = Number(discounts.get(rider.rider_type).discount_percent);
    const baseAfterDiscount = Math.floor((baseCents * discount + 50) / 100);
    let baseCharge = baseAfterDiscount;
    let transferCredit = 0;

    if (previous) {
      const ruleKey = `${previous.route_family}\t${route.route_family}`;
      const allowed = transferRules.get(ruleKey);
      if (allowed !== undefined && minutesBetween(previous.tapped_at, tap.tapped_at) <= Number(allowed)) {
        transferCredit = baseCharge;
        baseCharge = 0;
      }
    }

    const passSuppressed = tapOverrides.has("suppress_pass");
    let passCredit = 0;
    if (baseCharge > 0 && !passSuppressed && activePassCovers(passes, tap.rider_id, tap.service_date, serviceZone)) {
      passCredit = baseCharge;
      day.pass_credit_cents += passCredit;
      baseCharge = 0;
    }

    const disruptionCredit = disruptionCreditForTap(disruptions, tap, route, baseCharge);
    if (disruptionCredit > 0) {
      day.disruption_credit_cents += disruptionCredit;
      baseCharge -= disruptionCredit;
    }

    const subsidy = matchingSubsidy(subsidies, tap.rider_id, tap.service_date, serviceZone);
    let subsidyCredit = 0;
    if (baseCharge > 0 && subsidy) {
      const usageKey = subsidyMonthKey(subsidy, tap.service_date);
      const used = subsidyUsage.get(usageKey) || 0;
      const remainingLimit = Math.max(0, Number(subsidy.monthly_limit_cents) - used);
      const requestedCredit = Math.floor((baseCharge * Number(subsidy.percent) + 50) / 100);
      subsidyCredit = Math.min(baseCharge, requestedCredit, remainingLimit);
      if (subsidyCredit > 0) {
        day.subsidy_credit_cents += subsidyCredit;
        subsidyUsage.set(usageKey, used + subsidyCredit);
        baseCharge -= subsidyCredit;
      }
    }

    const exceptionResult = applyExceptionCredits(exceptions.get(tap.tap_id) || [], baseCharge, expressCents);
    baseCharge = exceptionResult.baseCharge;
    expressCents = exceptionResult.expressCents;
    if (exceptionResult.exceptionCredit > 0) {
      day.exception_credit_cents += exceptionResult.exceptionCredit;
    }

    tapAuditRows.push(tapAuditRow(tap, {
      route_family: route.route_family,
      base_after_discount_cents: baseAfterDiscount,
      transfer_credit_cents: transferCredit,
      pass_credit_cents: passCredit,
      disruption_credit_cents: disruptionCredit,
      subsidy_credit_cents: subsidyCredit,
      exception_credit_cents: exceptionResult.exceptionCredit,
      base_before_cap_cents: baseCharge,
      express_before_cap_cents: expressCents
    }));

    const routeFamily = getRouteFamily(day, route.route_family);
    routeFamily.preCapBaseCents += baseCharge;
    routeFamily.expressChargedCents += expressCents;
    routeFamily.tapCount += 1;
    routeFamily.zones.add(serviceZone);

    day.baseCharges.push(baseCharge);
    day.express_cents += expressCents;
    day.lastFareable = {
      route_family: route.route_family,
      station_id: tap.station_id,
      tapped_at: tap.tapped_at
    };
  }

  for (const adjustment of adjustments) {
    if (adjustment.approved !== true) continue;
    const day = getDay(days, adjustment.service_date, adjustment.rider_id);
    if (!day.rider_type && riders.has(adjustment.rider_id)) {
      day.rider_type = riders.get(adjustment.rider_id).rider_type;
    }
    day.adjustment_cents += Number(adjustment.amount_cents);
  }

  const sortedDays = Array.from(days.values()).sort((a, b) => (
    a.service_date.localeCompare(b.service_date) ||
    a.rider_id.localeCompare(b.rider_id)
  ));
  const routeFamilyRows = [];
  for (const day of sortedDays) {
    applySettlementHolds(day, holds);
  }
  applyCarryoverCredits(sortedDays, carryovers);
  applyFamilyMinimums(sortedDays, minimums);
  applyCapExclusions(sortedDays, capExclusions);

  for (const day of sortedDays) {
    const routeFamilies = [...day.routeFamilies.values()].sort((a, b) => (
      a.route_family.localeCompare(b.route_family)
    ));
    for (const family of routeFamilies) {
      family.capEligibleBaseCents = Math.max(0, family.preCapBaseCents - family.capExcludedBaseCents);
    }
    const baseTotal = routeFamilies.reduce((sum, family) => sum + family.capEligibleBaseCents, 0);
    day.expressTotalCents = routeFamilies.reduce((sum, family) => sum + family.expressChargedCents, 0);
    let cappedBase = baseTotal;
    day.cappingApplied = false;

    if (day.rider_type && day.zones.size > 0) {
      const applicableCaps = caps
        .filter((cap) => cap.rider_type === day.rider_type && day.zones.has(cap.service_zone))
        .map((cap) => Number(cap.cap_cents));
      if (applicableCaps.length > 0) {
        const cap = Math.max(...applicableCaps);
        if (baseTotal > cap) {
          cappedBase = cap;
          day.cappingApplied = true;
        }
      }
    }
    const capCredit = baseTotal - cappedBase;
    const capAllocations = allocateCapCredit(routeFamilies, capCredit);
    for (const family of routeFamilies) {
      const allocatedCap = capAllocations.get(family.route_family) || 0;
      family.capCreditCents = allocatedCap;
      family.capEligibleBaseAfterDailyCapCents = family.capEligibleBaseCents - allocatedCap;
      family.baseAfterDailyCapCents = family.capExcludedBaseCents + family.capEligibleBaseAfterDailyCapCents;
    }
  }

  const accountCapRows = applyAccountCaps(sortedDays, accountLinks, accountCaps);
  applyAccountCredits(sortedDays, accountLinks, accountCredits);

  const rows = sortedDays.map((day) => {
    const baseAfterAccountCredit = [...day.routeFamilies.values()]
      .reduce((sum, family) => sum + family.baseAfterDailyCapCents, 0);
    const expressAfterAccountCredit = [...day.routeFamilies.values()]
      .reduce((sum, family) => sum + family.expressChargedCents, 0);
    const routeFamilies = [...day.routeFamilies.values()].sort((a, b) => (
      a.route_family.localeCompare(b.route_family)
    ));
    for (const family of routeFamilies) {
      routeFamilyRows.push({
        service_date: family.service_date,
        rider_id: family.rider_id,
        route_family: family.route_family,
        base_charged_cents: family.baseAfterDailyCapCents,
        express_charged_cents: family.expressChargedCents,
        cap_credit_cents: family.capCreditCents,
        account_cap_credit_cents: family.accountCapCreditCents,
        account_credit_cents: family.accountCreditCents,
        tap_count: family.tapCount
      });
    }

    return {
      service_date: day.service_date,
      rider_id: day.rider_id,
      total_charged_cents: baseAfterAccountCredit + expressAfterAccountCredit + day.adjustment_cents,
      tap_count: day.tap_count,
      distinct_routes: day.distinctRoutes.size,
      capping_applied: day.cappingApplied,
      pass_credit_cents: day.pass_credit_cents,
      disruption_credit_cents: day.disruption_credit_cents,
      subsidy_credit_cents: day.subsidy_credit_cents,
      exception_credit_cents: day.exception_credit_cents,
      hold_credit_cents: day.hold_credit_cents,
      carryover_credit_cents: day.carryover_credit_cents,
      account_cap_credit_cents: day.account_cap_credit_cents,
      account_credit_cents: day.account_credit_cents,
      adjustment_cents: day.adjustment_cents,
      unresolved_count: day.unresolved_count
    };
  });

  fs.mkdirSync(outputDir, { recursive: true });
  const header = [
    "service_date",
    "rider_id",
    "total_charged_cents",
    "tap_count",
    "distinct_routes",
    "capping_applied",
    "pass_credit_cents",
    "disruption_credit_cents",
    "subsidy_credit_cents",
    "exception_credit_cents",
    "hold_credit_cents",
    "carryover_credit_cents",
    "account_cap_credit_cents",
    "account_credit_cents",
    "adjustment_cents",
    "unresolved_count"
  ];
  writeCsv(path.join(outputDir, "rider-day-settlement.csv"), header, rows);

  const routeFamilyHeader = [
    "service_date",
    "rider_id",
    "route_family",
    "base_charged_cents",
    "express_charged_cents",
    "cap_credit_cents",
    "account_cap_credit_cents",
    "account_credit_cents",
    "tap_count"
  ];
  writeCsv(path.join(outputDir, "route-family-ledger.csv"), routeFamilyHeader, routeFamilyRows);

  const accountCapHeader = [
    "service_date",
    "account_id",
    "service_zone",
    "base_before_account_cap_cents",
    "account_cap_cents",
    "account_cap_credit_cents",
    "participating_rider_days"
  ];
  writeCsv(path.join(outputDir, "account-cap-ledger.csv"), accountCapHeader, accountCapRows);

  const tapAuditHeader = [
    "tap_id",
    "service_date",
    "original_tapped_at",
    "tapped_at",
    "original_rider_id",
    "rider_id",
    "original_route_id",
    "route_id",
    "original_station_id",
    "station_id",
    "original_device_status",
    "device_status",
    "unresolved_reason",
    "route_family",
    "base_after_discount_cents",
    "transfer_credit_cents",
    "pass_credit_cents",
    "disruption_credit_cents",
    "subsidy_credit_cents",
    "exception_credit_cents",
    "base_before_cap_cents",
    "express_before_cap_cents"
  ];
  writeCsv(path.join(outputDir, "tap-audit-ledger.csv"), tapAuditHeader, tapAuditRows);

  const unresolvedCounts = {};
  for (const event of unresolvedEvents) {
    unresolvedCounts[event.reason] = (unresolvedCounts[event.reason] || 0) + 1;
  }
  unresolvedEvents.sort((a, b) => (
    a.service_date.localeCompare(b.service_date) ||
    a.tap_id.localeCompare(b.tap_id)
  ));

  const summary = {
    service_dates: [...new Set(rows.map((row) => row.service_date))].sort(),
    rider_day_count: rows.length,
    total_charged_cents: rows.reduce((sum, row) => sum + row.total_charged_cents, 0),
    total_pass_credit_cents: rows.reduce((sum, row) => sum + row.pass_credit_cents, 0),
    total_disruption_credit_cents: rows.reduce((sum, row) => sum + row.disruption_credit_cents, 0),
    total_subsidy_credit_cents: rows.reduce((sum, row) => sum + row.subsidy_credit_cents, 0),
    total_exception_credit_cents: rows.reduce((sum, row) => sum + row.exception_credit_cents, 0),
    total_hold_credit_cents: rows.reduce((sum, row) => sum + row.hold_credit_cents, 0),
    total_carryover_credit_cents: rows.reduce((sum, row) => sum + row.carryover_credit_cents, 0),
    total_account_cap_credit_cents: rows.reduce((sum, row) => sum + row.account_cap_credit_cents, 0),
    total_account_credit_cents: rows.reduce((sum, row) => sum + row.account_credit_cents, 0),
    total_adjustment_cents: rows.reduce((sum, row) => sum + row.adjustment_cents, 0),
    capped_rider_days: rows.filter((row) => row.capping_applied).length,
    account_capped_groups: accountCapRows.length,
    total_fareable_taps: rows.reduce((sum, row) => sum + row.tap_count, 0),
    corrected_tap_count: correctedTapIds.size,
    unresolved_by_reason: sortedObjectFromCounts(unresolvedCounts),
    unresolved_events: unresolvedEvents
  };

  fs.writeFileSync(path.join(outputDir, "settlement-summary.json"), JSON.stringify(summary, null, 2) + "\n");
}

main();
JS

node /app/reconcile.js
