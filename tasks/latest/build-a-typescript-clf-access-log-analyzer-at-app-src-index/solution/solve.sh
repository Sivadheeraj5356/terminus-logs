#!/bin/bash
set -euo pipefail

mkdir -p /app/src

cat > /app/src/index.ts << 'TSEOF'
import * as fs from 'fs';
import * as path from 'path';

const CLF_REGEX = /^(\S+) \S+ \S+ \[(\d{2}\/\w{3}\/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4})\] "([^"]*)" (\S+) (\S+) "[^"]*" "[^"]*"$/;

interface Entry {
  ip: string;
  method: string;
  url: string;
  status: number;
  bytes: number;
  utcHour: number;
}

function parseUtcHour(timestamp: string): number | null {
  const m = /^(\d{2})\/(\w{3})\/(\d{4}):(\d{2}):(\d{2}):(\d{2}) ([+-])(\d{2})(\d{2})$/.exec(timestamp);
  if (!m) return null;

  const day = parseInt(m[1], 10);
  const monthName = m[2];
  const year = parseInt(m[3], 10);
  const localHour = parseInt(m[4], 10);
  const localMin = parseInt(m[5], 10);
  const localSec = parseInt(m[6], 10);
  const sign = m[7] === '+' ? 1 : -1;
  const offsetHour = parseInt(m[8], 10);
  const offsetMinute = parseInt(m[9], 10);

  const monthIndex: Record<string, number> = {
    Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5,
    Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11,
  };
  const month = monthIndex[monthName];
  if (month === undefined) return null;
  if (localHour > 23 || localMin > 59 || localSec > 59) return null;
  if (offsetHour > 23 || offsetMinute > 59) return null;

  const daysInMonth = [31, isLeapYear(year) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (day < 1 || day > daysInMonth[month]) return null;

  const offsetMin = sign * (offsetHour * 60 + offsetMinute);
  const utcMin = localHour * 60 + localMin - offsetMin;
  return (Math.floor(utcMin / 60) % 24 + 24) % 24;
}

function isLeapYear(year: number): boolean {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
}

function parseLine(line: string): Entry | null {
  const m = CLF_REGEX.exec(line);
  if (!m) return null;

  const ip = m[1];
  const timestamp = m[2];
  const request = m[3];
  const statusStr = m[4];
  const bytesStr = m[5];

  if (!/^\d+$/.test(statusStr)) return null;
  const status = parseInt(statusStr, 10);
  if (status < 100 || status > 599) return null;

  let bytes: number;
  if (bytesStr === '-') {
    bytes = 0;
  } else if (/^\d+$/.test(bytesStr)) {
    bytes = parseInt(bytesStr, 10);
  } else {
    return null;
  }

  const parts = request.split(' ');
  if (parts.length !== 3 || parts.some((part) => part.length === 0)) return null;

  const rawUrl = parts[1];
  const qIdx = rawUrl.indexOf('?');
  const url = qIdx === -1 ? rawUrl : rawUrl.slice(0, qIdx);

  const utcHour = parseUtcHour(timestamp);
  if (utcHour === null) return null;

  return { ip, method: parts[0], url, status, bytes, utcHour };
}

function statusBucket(status: number): string {
  if (status < 200) return '1xx';
  if (status < 300) return '2xx';
  if (status < 400) return '3xx';
  if (status < 500) return '4xx';
  return '5xx';
}

function topFive(counts: Map<string, number>): Array<[string, number]> {
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 5);
}

function main(): void {
  const logsDir = '/app/logs';
  const outputFile = '/app/report.json';

  let totalRequests = 0;
  let invalidCount = 0;
  let errorRequests = 0;
  let totalBytes = 0;

  const statusBreakdown: Record<string, number> = {
    '1xx': 0, '2xx': 0, '3xx': 0, '4xx': 0, '5xx': 0,
  };
  const methodsBreakdown: Record<string, number> = {};
  const ipBytes = new Map<string, number>();
  const urlCounts = new Map<string, number>();
  const hourCounts: Record<string, number> = {};

  const files = fs.readdirSync(logsDir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.log'))
    .map((entry) => entry.name)
    .sort();

  for (const file of files) {
    const content = fs.readFileSync(path.join(logsDir, file), 'utf-8');
    for (const rawLine of content.split('\n')) {
      if (!rawLine.trim()) continue;
      const line = rawLine.endsWith('\r') ? rawLine.slice(0, -1) : rawLine;

      const entry = parseLine(line);
      if (!entry) {
        invalidCount++;
        continue;
      }

      totalRequests++;
      totalBytes += entry.bytes;
      if (entry.status >= 400) errorRequests++;

      statusBreakdown[statusBucket(entry.status)]++;
      methodsBreakdown[entry.method] = (methodsBreakdown[entry.method] ?? 0) + 1;
      ipBytes.set(entry.ip, (ipBytes.get(entry.ip) ?? 0) + entry.bytes);
      urlCounts.set(entry.url, (urlCounts.get(entry.url) ?? 0) + 1);

      const hourKey = String(entry.utcHour).padStart(2, '0');
      hourCounts[hourKey] = (hourCounts[hourKey] ?? 0) + 1;
    }
  }

  const topIpsByBytes = topFive(ipBytes).map(([ip, bytes]) => ({ ip, bytes }));
  const topUrls = topFive(urlCounts).map(([url, requests]) => ({ url, requests }));

  const report = {
    total_requests: totalRequests,
    invalid_count: invalidCount,
    error_requests: errorRequests,
    total_bytes_transferred: totalBytes,
    status_breakdown: statusBreakdown,
    methods_breakdown: methodsBreakdown,
    top_ips_by_bytes: topIpsByBytes,
    top_urls_by_requests: topUrls,
    hourly_requests: hourCounts,
  };

  fs.writeFileSync(outputFile, JSON.stringify(report, null, 2) + '\n');
}

main();
TSEOF

cd /app
/app/node_modules/.bin/tsc
node dist/index.js
