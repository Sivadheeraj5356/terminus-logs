#!/bin/bash
# Oracle patch: harden the Flask API, OpenAPI, Makefile, and Perl analyzer; add
# offline yq verification plus manifest-policy validation with deterministic
# quarantine reasons, risk score, and Merkle catalog reporting.
set -euo pipefail
cd /app

cat > config/media.yaml <<'YAML'
service:
  host: 127.0.0.1
  port: 5055
  debug: false
  cors_origins:
    - "https://media.example.test"
  api_key_header: X-API-Key
  api_key: media-local-build-token
  response_headers:
    cache_control: "no-store"
    x_content_type_options: "nosniff"
media:
  fixture_dir: fixtures
  allowed_extensions:
    - .png
    - .jpg
    - .jpeg
  include_absolute_paths: false
  policy:
    max_pixels: 24
    serve_only_manifest_valid: true
    reason_weights:
      missing_manifest: 13
      sha256: 11
      signature: 7
      format: 5
      width: 5
      height: 5
      mode: 5
      pixels: 3
      name_collision: 17
  manifest:
    - name: poster.jpg
      sha256: f2bd4acdeb3a0f36744ae32c5bf4479c623a9c6ca6a679daf32702679e704b29
      format: JPEG
      width: 2
      height: 5
      mode: RGB
      signature: 00cf600d9abbe024758ca21960f22cf8624aa8ee456363484ae3953e17c474d3
    - name: shore.png
      sha256: 7de429b0ddae5354ca11fd3d607a626762d26eeae355f8a32107e421b43f870e
      format: PNG
      width: 4
      height: 3
      mode: RGB
      signature: 561c4b7d9c7b8e1e6f5da320124d764582027326f36af24f143bdc8731477041
build:
  yq:
    version: v4.53.3
    artifact: yq_linux_amd64
    sha256: "84be51c2bf82b1eae16c54fab3f5d9aa887f5fb30d90990217e9031bf42f9f56"
    source: "vendor/yq_linux_amd64"
YAML

cat > api/app.py <<'PYAPP'
import hashlib
import os
import re
from collections import defaultdict
from pathlib import Path

import yaml
from flask import Flask, jsonify, request
from flask_cors import CORS
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "media.yaml"
REASON_ORDER = [
    "missing_manifest",
    "sha256",
    "signature",
    "format",
    "width",
    "height",
    "mode",
    "pixels",
    "name_collision",
]


def load_config():
    config_path = Path(os.environ.get("MEDIA_CONFIG", DEFAULT_CONFIG))
    with config_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_signature(entry: dict) -> str:
    text = "\n".join([
        "media-manifest-v1",
        str(entry.get("name", "")),
        str(entry.get("sha256", "")),
        str(entry.get("format", "")),
        str(entry.get("width", "")),
        str(entry.get("height", "")),
        str(entry.get("mode", "")),
    ]) + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def collision_id(name: str) -> str:
    stem = Path(name).stem.lower()
    return re.sub(r"[^a-z0-9]+", "-", stem).strip("-")


def image_records(config: dict):
    media = config.get("media", {})
    fixture_dir = (ROOT / media.get("fixture_dir", "fixtures")).resolve()
    allowed = {ext.lower() for ext in media.get("allowed_extensions", [".png", ".jpg", ".jpeg"])}
    records = []
    for file_path in sorted(fixture_dir.iterdir(), key=lambda p: p.name):
        if not file_path.is_file() or file_path.suffix.lower() not in allowed:
            continue
        with Image.open(file_path) as image:
            records.append({
                "name": file_path.name,
                "format": image.format,
                "width": int(image.width),
                "height": int(image.height),
                "mode": image.mode,
                "sha256": sha256_bytes(file_path),
            })
    return records


def classify_records(config: dict):
    media = config.get("media", {})
    policy = media.get("policy", {})
    max_pixels = int(policy.get("max_pixels", 24))
    manifest = {entry.get("name"): entry for entry in media.get("manifest", [])}
    records = image_records(config)
    ids = defaultdict(list)
    for rec in records:
        ids[collision_id(rec["name"])].append(rec["name"])
    collisions = {name for names in ids.values() if len(names) > 1 for name in names}
    accepted = []
    quarantined = []
    for rec in records:
        entry = manifest.get(rec["name"])
        reasons = []
        if entry is None:
            reasons.append("missing_manifest")
        else:
            if str(entry.get("sha256", "")) != rec["sha256"]:
                reasons.append("sha256")
            if str(entry.get("signature", "")) != manifest_signature(entry):
                reasons.append("signature")
            for field in ("format", "width", "height", "mode"):
                if str(entry.get(field, "")) != str(rec[field]):
                    reasons.append(field)
        if rec["width"] * rec["height"] > max_pixels:
            reasons.append("pixels")
        if rec["name"] in collisions:
            reasons.append("name_collision")
        reasons = [reason for reason in REASON_ORDER if reason in reasons]
        item = {key: rec[key] for key in ["name", "format", "width", "height", "mode"]}
        if reasons:
            quarantined.append({"name": rec["name"], "reasons": reasons})
        else:
            accepted.append(item)
    return sorted(accepted, key=lambda x: x["name"]), sorted(quarantined, key=lambda x: x["name"])


CONFIG = load_config()
SERVICE = CONFIG.get("service", {})
API_KEY_HEADER = SERVICE.get("api_key_header", "X-API-Key")
API_KEY = SERVICE.get("api_key", "")

app = Flask(__name__)
app.config["DEBUG"] = False
_origins = SERVICE.get("cors_origins", [])
if not _origins or "*" in _origins:
    _origins = []
CORS(app, resources={r"/*": {"origins": _origins}})


@app.after_request
def add_headers(response):
    headers = SERVICE.get("response_headers", {})
    response.headers["Cache-Control"] = headers.get("cache_control", "no-store")
    response.headers["X-Content-Type-Options"] = headers.get("x_content_type_options", "nosniff")
    return response


@app.get("/health")
def health():
    return jsonify({"status": "ok", "debug": False, "cors_origins": SERVICE.get("cors_origins", [])})


@app.get("/media")
def media_index():
    if not API_KEY or request.headers.get(API_KEY_HEADER) != API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    accepted, _ = classify_records(CONFIG)
    return jsonify({"count": len(accepted), "items": accepted, "request_origin": request.headers.get("Origin", "")})


if __name__ == "__main__":
    app.run(host=SERVICE.get("host", "127.0.0.1"), port=int(os.environ.get("PORT", SERVICE.get("port", 5055))), debug=False)
PYAPP

cat > openapi.yaml <<'YAML'
openapi: 3.1.0
info:
  title: Media Metadata API
  version: 1.4.0
servers:
  - url: http://127.0.0.1:5055
paths:
  /health:
    get:
      responses:
        "200":
          description: health response
  /media:
    get:
      security:
        - ApiKeyAuth: []
      responses:
        "200":
          description: authenticated policy-accepted image metadata
        "401":
          description: missing or invalid API key
components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
YAML

cat > Makefile <<'MAKE'
REPORT := build/hardened-report.json
CONFIG := config/media.yaml
OPENAPI := openapi.yaml
PORT ?= 5055
YQ_BIN := .tools/yq

.PHONY: report clean run bootstrap-yq

report: bootstrap-yq
	mkdir -p build
	perl scripts/analyze.pl --yq "$(YQ_BIN)" --config "$(CONFIG)" --openapi "$(OPENAPI)" --port "$(PORT)" --report "$(REPORT)"

bootstrap-yq:
	perl scripts/analyze.pl --bootstrap-only --yq "$(YQ_BIN)" --config "$(CONFIG)"

run:
	MEDIA_CONFIG=$(CONFIG) PORT=$(PORT) python api/app.py

clean:
	rm -rf build .tools
MAKE

cat > scripts/analyze.pl <<'PERL'
#!/usr/bin/env perl
use strict;
use warnings;
use Digest::SHA qw(sha256_hex);
use File::Basename qw(dirname);
use File::Copy qw(copy);
use File::Path qw(make_path);
use File::Spec;
use File::Temp qw(tempfile);
use Getopt::Long qw(GetOptions);
use HTTP::Tiny;
use IPC::Open3;
use JSON::PP qw(decode_json encode_json);
use Symbol qw(gensym);

my ($yq, $config, $openapi, $port, $report, $bootstrap_only) = ('.tools/yq', 'config/media.yaml', 'openapi.yaml', 5055, 'build/hardened-report.json', 0);
GetOptions(
  'yq=s' => \$yq,
  'config=s' => \$config,
  'openapi=s' => \$openapi,
  'port=i' => \$port,
  'report=s' => \$report,
  'bootstrap-only' => \$bootstrap_only,
) or die "bad options\n";

my @reason_order = qw(missing_manifest sha256 signature format width height mode pixels name_collision);
my %reason_rank = map { $reason_order[$_] => $_ } 0..$#reason_order;
my @manifest_field_order = qw(sha256 signature format width height mode);
my %manifest_field_rank = map { $manifest_field_order[$_] => $_ } 0..$#manifest_field_order;
my %default_weights = (missing_manifest => 13, sha256 => 11, signature => 7, format => 5, width => 5, height => 5, mode => 5, pixels => 3, name_collision => 17);

sub slurp {
  my ($p) = @_;
  open my $fh, '<', $p or die "cannot read $p: $!";
  binmode $fh;
  local $/;
  return <$fh>;
}

sub run_capture {
  my (@cmd) = @_;
  my $err = gensym;
  my $pid = open3(my $in, my $out, $err, @cmd);
  close $in;
  my $stdout = do { local $/; <$out> // '' };
  my $stderr = do { local $/; <$err> // '' };
  waitpid($pid, 0);
  die "command failed @cmd\n$stderr" if $? != 0;
  return $stdout;
}

sub json_bool { return $_[0] ? JSON::PP::true : JSON::PP::false; }

sub temp_json_file {
  my ($body) = @_;
  my ($fh, $name) = tempfile();
  print {$fh} $body;
  close $fh;
  return $name;
}

sub config_field {
  my ($name) = @_;
  my $txt = slurp($config);
  my @matches = ($txt =~ /^\s*$name:\s*["']?([^"'\s]+)["']?\s*$/mg);
  return @matches ? $matches[-1] : undef;
}

sub bootstrap_yq {
  my $source = config_field('source');
  my $want = config_field('sha256');
  my $version = config_field('version');
  die "missing pinned local yq fields" unless $source && $want && $version;
  die "bad sha256" unless $want =~ /^[a-f0-9]{64}$/;
  die "bad yq source" if $source =~ m{^https?://};
  my $source_path = File::Spec->file_name_is_absolute($source) ? $source : File::Spec->catfile('.', $source);
  die "missing bundled yq artifact $source_path" unless -f $source_path;
  my $source_sha = sha256_hex(slurp($source_path));
  die "bundled yq checksum mismatch: got $source_sha want $want" unless $source_sha eq $want;
  make_path(dirname($yq));
  copy($source_path, $yq) or die "cannot copy $source_path to $yq: $!";
  chmod 0755, $yq or die "chmod $yq: $!";
  my $installed_sha = sha256_hex(slurp($yq));
  die "installed yq checksum mismatch" unless $installed_sha eq $want;
  return ($version, $want);
}

sub yaml_value {
  my ($expr) = @_;
  my $out = run_capture($yq, '-r', $expr, $config);
  chomp $out;
  return $out;
}

sub yaml_json {
  my ($expr) = @_;
  return decode_json(run_capture($yq, '-o=json', $expr, $config));
}

sub manifest_signature {
  my ($entry) = @_;
  my @parts = ('media-manifest-v1', map { ($entry->{$_} // '') . '' } qw(name sha256 format width height mode));
  return sha256_hex(join("\n", @parts) . "\n");
}

sub collision_id {
  my ($name) = @_;
  $name =~ s/\.[^.]+$//;
  $name = lc $name;
  $name =~ s/[^a-z0-9]+/-/g;
  $name =~ s/^-+|-+$//g;
  return $name;
}

sub sorted_reasons {
  my (@fields) = @_;
  my %seen;
  return [sort { $reason_rank{$a} <=> $reason_rank{$b} } grep { !$seen{$_}++ } @fields];
}

sub sorted_manifest_fields {
  my (@fields) = @_;
  my %seen;
  return [sort { $manifest_field_rank{$a} <=> $manifest_field_rank{$b} } grep { !$seen{$_}++ } @fields];
}

sub fixture_records {
  my ($fixture_dir, $allowed) = @_;
  my $code = <<'PYCODE';
import hashlib, json, sys
from pathlib import Path
from PIL import Image
fixture = Path(sys.argv[1])
allowed = set(json.loads(sys.argv[2]))
out = []
for path in sorted(fixture.iterdir(), key=lambda p: p.name):
    if not path.is_file() or path.suffix.lower() not in allowed:
        continue
    with Image.open(path) as im:
        out.append({
            "name": path.name,
            "format": im.format,
            "width": int(im.width),
            "height": int(im.height),
            "mode": im.mode,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
print(json.dumps(out, separators=(",", ":")))
PYCODE
  return decode_json(run_capture('python3', '-c', $code, $fixture_dir, encode_json($allowed)));
}

sub classify_policy {
  my ($manifest, $records, $policy) = @_;
  my %manifest_by = map { $_->{name} => $_ } @$manifest;
  my %weights = (%default_weights, %{ $policy->{reason_weights} || {} });
  my $max_pixels = int($policy->{max_pixels} // 24);
  my %ids;
  for my $rec (@$records) { push @{ $ids{collision_id($rec->{name})} }, $rec->{name}; }
  my %collide;
  for my $names (values %ids) { if (@$names > 1) { $collide{$_} = 1 for @$names; } }
  my (@accepted, @quarantined);
  for my $rec (sort { $a->{name} cmp $b->{name} } @$records) {
    my @reasons;
    my $entry = $manifest_by{$rec->{name}};
    if (!$entry) { push @reasons, 'missing_manifest'; }
    else {
      push @reasons, 'sha256' if (($entry->{sha256} // '') ne ($rec->{sha256} // ''));
      push @reasons, 'signature' if (($entry->{signature} // '') ne manifest_signature($entry));
      for my $field (qw(format width height mode)) {
        push @reasons, $field if (($entry->{$field} // '') . '') ne (($rec->{$field} // '') . '');
      }
    }
    push @reasons, 'pixels' if int($rec->{width}) * int($rec->{height}) > $max_pixels;
    push @reasons, 'name_collision' if $collide{$rec->{name}};
    my $ordered = sorted_reasons(@reasons);
    if (@$ordered) { push @quarantined, { name => $rec->{name}, reasons => $ordered }; }
    else { push @accepted, { map { $_ => $rec->{$_} } qw(name format width height mode) }; }
  }
  my $risk = 0;
  for my $q (@quarantined) { $risk += ($weights{$_} // 0) for @{ $q->{reasons} }; }
  return (\@accepted, \@quarantined, $risk);
}

sub catalog_merkle_root {
  my ($items, $content_sha) = @_;
  my @leaves;
  for my $item (@$items) {
    my $name = $item->{name};
    push @leaves, sha256_hex(join("\n", 'media-leaf-v2', $name, $item->{format}, $item->{width}, $item->{height}, $item->{mode}, ($content_sha->{$name} // '')) . "\n");
  }
  return sha256_hex("media-empty-v2\n") unless @leaves;
  while (@leaves > 1) {
    my @next;
    while (@leaves) {
      my $left = shift @leaves;
      my $right = @leaves ? shift @leaves : $left;
      push @next, sha256_hex("media-node-v2\n$left\n$right\n");
    }
    @leaves = @next;
  }
  return $leaves[0];
}

sub manifest_report {
  my ($manifest, $records) = @_;
  my %manifest_by = map { $_->{name} => $_ } @$manifest;
  my %records_by = map { $_->{name} => $_ } @$records;
  my @expected = sort keys %manifest_by;
  my @current = sort keys %records_by;
  my @missing = sort grep { !exists $records_by{$_} } @expected;
  my @unexpected = sort grep { !exists $manifest_by{$_} } @current;
  my %content = map { $_->{name} => $_->{sha256} } @$records;
  my @mismatches;
  for my $name (sort grep { exists $records_by{$_} } @expected) {
    my $decl = $manifest_by{$name};
    my $rec = $records_by{$name};
    my @fields;
    push @fields, 'sha256' if (($decl->{sha256} // '') ne ($rec->{sha256} // ''));
    push @fields, 'signature' if (($decl->{signature} // '') ne manifest_signature($decl));
    for my $field (qw(format width height mode)) {
      push @fields, $field if (($decl->{$field} // '') . '') ne (($rec->{$field} // '') . '');
    }
    push @mismatches, { name => $name, fields => sorted_manifest_fields(@fields) } if @fields;
  }
  my $passed = !@missing && !@unexpected && !@mismatches;
  return ({
    declared_count => scalar(@$manifest),
    expected_names => \@expected,
    missing_files => \@missing,
    unexpected_files => \@unexpected,
    mismatches => \@mismatches,
    content_sha256 => \%content,
    passed => json_bool($passed),
  }, $passed);
}

my ($pin_version, $pin_sha) = bootstrap_yq();
exit 0 if $bootstrap_only;

$pin_version = yaml_value('.build.yq.version');
$pin_sha = yaml_value('.build.yq.sha256');
my $debug = yaml_value('.service.debug') eq 'true';
my $host = yaml_value('.service.host');
my $api_key_header = yaml_value('.service.api_key_header');
my $api_key = yaml_value('.service.api_key');
my $fixture_dir = yaml_value('.media.fixture_dir');
my $leaks_paths = yaml_value('.media.include_absolute_paths') eq 'true';
my $cors = yaml_json('.service.cors_origins');
my $manifest = yaml_json('.media.manifest');
my $policy = yaml_json('.media.policy');
my $allowed = yaml_json('.media.allowed_extensions');
my $cors_wildcard = grep { $_ eq '*' } @$cors;
my $version_text = run_capture($yq, '--version');
my $records = fixture_records($fixture_dir, $allowed);

my $pid = fork();
die "fork failed: $!" unless defined $pid;
if ($pid == 0) {
  $ENV{MEDIA_CONFIG} = $config;
  $ENV{PORT} = $port;
  open STDOUT, '>', '/tmp/media-api.out';
  open STDERR, '>', '/tmp/media-api.err';
  exec('python', 'api/app.py') or die "exec api failed: $!";
}

my $base = "http://127.0.0.1:$port";
delete @ENV{qw(http_proxy HTTP_PROXY https_proxy HTTPS_PROXY all_proxy ALL_PROXY)};
$ENV{NO_PROXY} = '127.0.0.1,localhost';
my $http = HTTP::Tiny->new(timeout => 2);
my $health_body;
for (1..60) {
  my $h = $http->get("$base/health");
  if ($h->{success}) { $health_body = $h->{content}; last; }
  select undef, undef, undef, 0.25;
}
die "api did not start" unless defined $health_body;
my $unauth = $http->get("$base/media", { headers => { Origin => 'https://media.example.test' } });
my $m = $http->get("$base/media", { headers => { Origin => 'https://media.example.test', $api_key_header => $api_key } });
my $media_body = $m->{content} // '{}';
kill 'TERM', $pid;
waitpid($pid, 0);

my $health_file = temp_json_file($health_body);
my $media_file = temp_json_file($media_body);
my $health_status = run_capture('jq', '-r', '.status', $health_file); chomp $health_status;
my $api_debug = run_capture('jq', '-r', '.debug', $health_file) eq "true\n";
my $media_count = run_capture('jq', '-r', '.count', $media_file); chomp $media_count;
my $path_leaks = run_capture('jq', '-r', '[.items[] | has("absolute_path")] | map(select(. == true)) | length', $media_file); chomp $path_leaks;
my $formats_json = run_capture('jq', '-c', '[.items[].format]', $media_file); chomp $formats_json;
my $items_json = run_capture('jq', '-c', '.items', $media_file); chomp $items_json;
my $catalog_json = run_capture('jq', '-c', '[.items[] | {name:.name,format:.format,width:.width,height:.height,mode:.mode}]', $media_file); chomp $catalog_json;
my $catalog_sha = sha256_hex($catalog_json);
my $formats = decode_json($formats_json);
my $items = decode_json($items_json);
unlink $health_file, $media_file;

my ($accepted, $quarantined, $risk_score) = classify_policy($manifest, $records, $policy);
my ($manifest_report, $manifest_passed) = manifest_report($manifest, $records);
my $policy_passed = !@$quarantined;
my $merkle = catalog_merkle_root($items, $manifest_report->{content_sha256});
my $auth_required = ($unauth->{status} || 0) == 401;
my $passed = (!$debug && !$cors_wildcard && !$leaks_paths && !$api_debug && $auth_required && $path_leaks == 0 && $host =~ /^(127\.0\.0\.1|localhost)$/ && $catalog_sha =~ /^[a-f0-9]{64}$/ && $manifest_passed && $policy_passed && int($media_count) == scalar(@$accepted));
my %out = (
  yq => { path => $yq, version => $pin_version, sha256 => $pin_sha, version_output => $version_text },
  tools => { yq_used => JSON::PP::true, jq_used => JSON::PP::true },
  config => { debug => json_bool($debug), host => $host, cors_wildcard => json_bool($cors_wildcard), leaks_absolute_paths => json_bool($leaks_paths) },
  api => {
    health_status => $health_status,
    debug => json_bool($api_debug),
    auth_required => json_bool($auth_required),
    unauthorized_status => int($unauth->{status} || 0),
    media_count => int($media_count || 0),
    absolute_path_leaks => int($path_leaks || 0),
    formats => $formats,
    catalog_sha256 => $catalog_sha,
  },
  manifest => $manifest_report,
  policy => {
    passed => json_bool($policy_passed),
    accepted_names => [map { $_->{name} } @$accepted],
    quarantined => $quarantined,
    risk_score => int($risk_score),
    catalog_merkle_root => $merkle,
  },
  security => { passed => json_bool($passed) },
);
make_path(dirname($report));
open my $outfh, '>', $report or die "cannot write $report: $!";
print {$outfh} encode_json(\%out);
close $outfh;
die "security checks failed\n" unless $passed;
PERL
chmod +x scripts/analyze.pl
