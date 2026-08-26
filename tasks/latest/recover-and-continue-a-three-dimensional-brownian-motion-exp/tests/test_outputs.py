from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import subprocess
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pytest

APP = Path('/app/environment')
RUN = APP / 'run.sh'
FIXTURES = APP / 'fixtures'
INSPECT_CLASSES = Path('/tmp/diffusion-inspector-classes')
INSPECT_CP = f"{INSPECT_CLASSES}:/app/lib/duckdb_jdbc.jar"
TOP_KEYS = [
    'schema', 'simulation', 'recovery', 'sourceSha256', 'stateSha256',
    'datasetSha256', 'msd', 'regression'
]


def setup_module():
    subprocess.run([str(APP / 'build.sh')], check=True)
    if INSPECT_CLASSES.exists():
        import shutil
        shutil.rmtree(INSPECT_CLASSES)
    INSPECT_CLASSES.mkdir(parents=True)
    sources = [str(path) for path in Path(__file__).parent.glob('*.java')]
    subprocess.run([
        'javac', '--release', '17', '-cp', '/app/lib/duckdb_jdbc.jar',
        '-d', str(INSPECT_CLASSES), *sources
    ], check=True)


def crc(preimage: str) -> str:
    import zlib
    return f'{zlib.crc32(preimage.encode()) & 0xffffffff:08x}'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canon_num(value: float) -> str:
    if value == 0:
        return '0'
    decimal = Decimal(str(value)).normalize()
    rendered = format(decimal, 'f')
    if '.' in rendered:
        rendered = rendered.rstrip('0').rstrip('.')
    return rendered


def record(tick: int, particle: str, xyz, *, corrupt=False, text=None) -> str:
    values = [f'{value:.6f}' for value in xyz] if text is None else list(text)
    preimage = '|'.join([str(tick), particle, *values])
    return 'R|' + preimage + '|' + ('00000000' if corrupt else crc(preimage))


def make_definition(*, dt=0.2, box=10.0, particles=('a', 'b', 'c', 'd'), fit=(1, 3), shards=()):
    lines = [
        'Bootstrap: docker', 'From: scratch', '%post',
        f"@@META|dt={dt}|dimensions=3|box={box}|particles={','.join(particles)}|fit={fit[0]}:{fit[1]}"
    ]
    for shard_id, generation, rows, closed in shards:
        lines.append(f'@@SHARD|id={shard_id}|generation={generation}')
        lines.extend(rows)
        if closed:
            lines.append('@@END_SHARD')
    return '\n'.join(lines) + '\n'


def dynamic_experiment(seed: int, token: str):
    safe = ''.join(ch for ch in token if ch.isalnum())[:10] or f'case{seed}'
    particles = tuple(f'{safe}_p{i}' for i in range(4))
    box = 8.0 + seed % 4
    positions = {}
    for tick in range(12):
        for index, particle in enumerate(particles):
            positions[tick, particle] = tuple(
                (0.7 + index * (1.13 + axis * 0.19) + tick * (0.61 - axis * 0.17)
                 + ((seed + index * 7 + tick * 3 + axis * 11) % 9 - 4) * 0.031) % box
                for axis in range(3)
            )

    base_rows = []
    for tick in range(9):
        for particle in particles:
            if tick == 4 and particle == particles[2]:
                continue
            base_rows.append(record(tick, particle, positions[tick, particle]))
    wrong = list(positions[3, particles[0]])
    wrong[0] = (wrong[0] + 1.25) % box
    base_rows.extend([
        record(3, particles[0], wrong),
        'R|malformed|row',
        record(2, 'unknown_' + safe, (1, 1, 1)),
        record(5, particles[1], positions[5, particles[1]], corrupt=True),
    ])
    initial = make_definition(
        box=box, particles=particles, fit=(1, 3),
        shards=[('base_' + safe, 0, base_rows, True)]
    )

    repair_rows = [
        record(3, particles[0], positions[3, particles[0]]),
        record(4, particles[2], positions[4, particles[2]]),
        record(4, particles[2], positions[4, particles[2]]),
    ]
    tail_rows = [
        record(tick, particle, positions[tick, particle])
        for tick in range(9, 12) for particle in particles
    ]
    extended = make_definition(
        box=box, particles=particles, fit=(1, 3),
        shards=[
            ('base_' + safe, 0, base_rows, True),
            ('repair_' + safe, 1, repair_rows, True),
            ('tail_' + safe, 0, tail_rows, False),
        ]
    )
    return initial, extended, particles


def parse_definition(text: str):
    meta = None
    current = None
    shards = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('@@META|'):
            if meta is not None or current is not None:
                raise ValueError('metadata')
            values = dict(part.split('=', 1) for part in line.split('|')[1:])
            meta = {
                'dt': float(values['dt']), 'box': float(values['box']),
                'particles': values['particles'].split(','),
                'fit': tuple(map(int, values['fit'].split(':'))),
            }
        elif line.startswith('@@SHARD|'):
            if current is not None:
                shards.append(current)
            values = dict(part.split('=', 1) for part in line.split('|')[1:])
            current = {'id': values['id'], 'generation': int(values['generation']), 'records': []}
        elif line == '@@END_SHARD':
            if current is None:
                raise ValueError('terminator')
            shards.append(current)
            current = None
        elif line.startswith('R|'):
            if current is None:
                raise ValueError('outside')
            current['records'].append(line)
    if current is not None:
        shards.append(current)
    if meta is None or not shards or len({s['id'] for s in shards}) != len(shards):
        raise ValueError('definition')
    for shard in shards:
        shard['records'].sort()
        shard['sha256'] = sha((''.join(row + '\n' for row in shard['records'])).encode())
    shards.sort(key=lambda shard: (shard['generation'], shard['id']))
    meta_line = (
        f"meta|dt={canon_num(meta['dt'])}|box={canon_num(meta['box'])}"
        f"|particles={','.join(meta['particles'])}|fit={meta['fit'][0]}:{meta['fit'][1]}"
    )
    body = meta_line + '\n'
    for shard in shards:
        body += (
            f"shard|id={shard['id']}|generation={shard['generation']}"
            f"|records={len(shard['records'])}|sha256={shard['sha256']}\n"
        )
        for row in shard['records']:
            encoded = base64.urlsafe_b64encode(row.encode()).decode().rstrip('=')
            body += f'record|{encoded}\n'
    source_hash = sha(body.encode())
    prefix = 'schema|brownian-recovery-state/v2\n' + body + f'sourceSha256|{source_hash}\n'
    state_hash = sha(prefix.encode())
    state_text = prefix + f'stateSha256|{state_hash}\n'
    return {'meta': meta, 'shards': shards, 'sourceSha256': source_hash,
            'stateSha256': state_hash, 'stateText': state_text}


def recover(state):
    meta = state['meta']
    counts = {
        'shardsSeen': len(state['shards']), 'recordsSeen': 0, 'recordsValid': 0,
        'recordsRejectedMalformed': 0, 'recordsRejectedCrc': 0,
        'recordsRejectedUnknownParticle': 0, 'supersededDiscarded': 0,
        'duplicatesDiscarded': 0, 'conflictingKeys': 0,
    }
    valid = []
    ticks = set()
    for shard in state['shards']:
        for line in shard['records']:
            counts['recordsSeen'] += 1
            parts = line.split('|')
            if len(parts) != 7 or parts[0] != 'R' or not re.fullmatch(r'[0-9a-f]{8}', parts[6]):
                counts['recordsRejectedMalformed'] += 1
                continue
            try:
                tick = int(parts[1])
                xyz = tuple(map(float, parts[3:6]))
            except ValueError:
                counts['recordsRejectedMalformed'] += 1
                continue
            if tick < 0 or not all(math.isfinite(v) and 0 <= v < meta['box'] for v in xyz):
                counts['recordsRejectedMalformed'] += 1
                continue
            if crc('|'.join(parts[1:6])) != parts[6]:
                counts['recordsRejectedCrc'] += 1
                continue
            if parts[2] not in meta['particles']:
                counts['recordsRejectedUnknownParticle'] += 1
                continue
            counts['recordsValid'] += 1
            ticks.add(tick)
            valid.append((tick, parts[2], *xyz, shard['generation'], shard['id']))
    grouped = defaultdict(list)
    for row in valid:
        grouped[row[:2]].append(row)
    selected = {}
    conflicts = set()
    for key, rows in grouped.items():
        highest = max(row[5] for row in rows)
        high = []
        for row in rows:
            if row[5] == highest:
                high.append(row)
            else:
                counts['supersededDiscarded'] += 1
        if len({row[2:5] for row in high}) > 1:
            counts['conflictingKeys'] += 1
            conflicts.add(key)
            continue
        high.sort(key=lambda row: row[6])
        selected[key] = high[0]
        counts['duplicatesDiscarded'] += len(high) - 1
    complete, rejected = [], []
    for tick in sorted(ticks):
        conflict = any((tick, particle) in conflicts for particle in meta['particles'])
        missing = any((tick, particle) not in selected for particle in meta['particles'])
        if not conflict and not missing:
            complete.append(tick)
        else:
            rejected.append({'tick': tick, 'reason': 'conflicting-record' if conflict else 'missing-particle'})
    selected_rows = sorted(selected.values(), key=lambda row: (row[0], row[1]))
    return counts, selected_rows, complete, rejected


def minimum_image(delta, box):
    while delta > box / 2:
        delta -= box
    while delta <= -box / 2:
        delta += box
    return delta


def regress(rows, key):
    xs = [row['time'] for row in rows]
    ys = [row[key] for row in rows]
    n = len(rows)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    intercept = my - slope * mx
    sse = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    sst = sum((y - my) ** 2 for y in ys)
    r2 = 1.0 if sst == 0 and sse == 0 else (0.0 if sst == 0 else 1 - sse / sst)
    stderr = ((sse / (n - 2)) / sxx) ** 0.5
    return slope, intercept, r2, stderr


def reference(text: str):
    state = parse_definition(text)
    meta = state['meta']
    counts, selected_rows, complete, rejected = recover(state)
    selected = {(row[0], row[1]): row for row in selected_rows}
    segments, current = [], []
    for tick in complete:
        if current and tick != current[-1] + 1:
            segments.append(current)
            current = []
        current.append(tick)
    if current:
        segments.append(current)
    points, unwrapped = [], {}
    for segment_id, segment in enumerate(segments):
        u = {particle: [0.0, 0.0, 0.0] for particle in meta['particles']}
        for index, tick in enumerate(segment):
            drift = [0.0, 0.0, 0.0]
            if index:
                before_tick = segment[index - 1]
                steps = {}
                for particle in meta['particles']:
                    before, after = selected[before_tick, particle], selected[tick, particle]
                    step = [minimum_image(after[2 + axis] - before[2 + axis], meta['box']) for axis in range(3)]
                    steps[particle] = step
                    for axis in range(3):
                        drift[axis] += step[axis]
                drift = [value / len(meta['particles']) for value in drift]
                for particle in meta['particles']:
                    for axis in range(3):
                        u[particle][axis] += steps[particle][axis] - drift[axis]
            unwrapped[tick] = {particle: tuple(u[particle]) for particle in meta['particles']}
            for particle in meta['particles']:
                row = selected[tick, particle]
                points.append((segment_id, tick, particle, *row[2:5], *u[particle], *drift))
    msd = []
    for lag in range(1, meta['fit'][1] + 1):
        sums = [0.0, 0.0, 0.0]
        pairs = 0
        for segment in segments:
            tick_set = set(segment)
            for tick in segment:
                if tick + lag not in tick_set:
                    continue
                for particle in meta['particles']:
                    before, after = unwrapped[tick][particle], unwrapped[tick + lag][particle]
                    for axis in range(3):
                        sums[axis] += (after[axis] - before[axis]) ** 2
                    pairs += 1
        if pairs:
            msd.append({'lag': lag, 'time': lag * meta['dt'], 'pairs': pairs,
                        'msdX': sums[0] / pairs, 'msdY': sums[1] / pairs,
                        'msdZ': sums[2] / pairs, 'msdTotal': sum(sums) / pairs})
    fit = [row for row in msd if meta['fit'][0] <= row['lag'] <= meta['fit'][1]]
    if len(fit) < 3:
        raise RuntimeError('insufficient')
    total, x, y, z = (regress(fit, key) for key in ('msdTotal', 'msdX', 'msdY', 'msdZ'))
    complete_set = set(complete)
    dataset_preimage = ''.join(
        f'{row[0]}|{row[1]}|{canon_num(row[2])}|{canon_num(row[3])}|{canon_num(row[4])}\n'
        for row in selected_rows if row[0] in complete_set
    )
    return {
        'state': state, 'counts': counts, 'selected': selected_rows, 'complete': complete,
        'rejected': rejected, 'points': points, 'msd': msd,
        'datasetSha256': sha(dataset_preimage.encode()),
        'regression': {'lags': [row['lag'] for row in fit], 'slope': total[0],
                       'intercept': total[1], 'r2': total[2], 'stderr': total[3],
                       'diffusion': total[0] / 6, 'diffusionErr': total[3] / 6,
                       'x': x[0] / 2, 'y': y[0] / 2, 'z': z[0] / 2}
    }


def run_mode(tmp_path: Path, mode: str, *, text=None, name='case', state=None, db=None, report=None):
    state = state or tmp_path / f'{name}.state'
    db = db or tmp_path / f'{name}.duckdb'
    report = report or tmp_path / f'{name}.json'
    args = [str(RUN), mode]
    if mode != 'rebuild':
        spec = tmp_path / f'{name}.def'
        spec.write_text(text)
        args += ['--spec', str(spec)]
    args += ['--state', str(state), '--db', str(db), '--report', str(report)]
    proc = subprocess.run(args, text=True, capture_output=True)
    return proc, state, db, report


def query(db: Path, sql: str):
    proc = subprocess.run(['java', '-cp', INSPECT_CP, 'DbInspector', str(db), sql],
                          text=True, capture_output=True, check=True)
    return [line.split('\x1f') for line in proc.stdout.splitlines()]


def approx(value):
    return pytest.approx(value, abs=5e-9, rel=1e-9)


def assert_report(report, ref):
    assert list(report) == TOP_KEYS
    assert report['schema'] == 'brownian-diffusion-report/v2'
    assert list(report['simulation']) == ['dimensions', 'dt', 'boxLength', 'particles', 'fitLagStart', 'fitLagEnd']
    assert report['simulation']['dimensions'] == 3
    assert report['simulation']['dt'] == approx(ref['state']['meta']['dt'])
    assert report['simulation']['boxLength'] == approx(ref['state']['meta']['box'])
    assert report['simulation']['particles'] == ref['state']['meta']['particles']
    assert report['simulation']['fitLagStart'] == ref['state']['meta']['fit'][0]
    assert report['simulation']['fitLagEnd'] == ref['state']['meta']['fit'][1]
    recovery = report['recovery']
    assert list(recovery) == [
        'shardsSeen', 'recordsSeen', 'recordsValid', 'recordsRejectedMalformed',
        'recordsRejectedCrc', 'recordsRejectedUnknownParticle', 'supersededDiscarded',
        'duplicatesDiscarded', 'conflictingKeys', 'shardsApplied',
        'completeTimesteps', 'rejectedTimesteps'
    ]
    for key, value in ref['counts'].items():
        assert recovery[key] == value
    assert recovery['shardsApplied'] == [
        {'id': shard['id'], 'generation': shard['generation'], 'records': len(shard['records']), 'sha256': shard['sha256']}
        for shard in ref['state']['shards']
    ]
    assert recovery['completeTimesteps'] == ref['complete']
    assert recovery['rejectedTimesteps'] == ref['rejected']
    assert report['sourceSha256'] == ref['state']['sourceSha256']
    assert report['stateSha256'] == ref['state']['stateSha256']
    assert report['datasetSha256'] == ref['datasetSha256']
    assert [row['lag'] for row in report['msd']] == [row['lag'] for row in ref['msd']]
    for got, expected in zip(report['msd'], ref['msd']):
        assert list(got) == ['lag', 'time', 'pairs', 'msdX', 'msdY', 'msdZ', 'msdTotal']
        assert got['lag'] == expected['lag'] and got['pairs'] == expected['pairs']
        for key in ('time', 'msdX', 'msdY', 'msdZ', 'msdTotal'):
            assert got[key] == approx(expected[key])
    regression = report['regression']
    expected = ref['regression']
    assert regression['lagsUsed'] == expected['lags']
    for got, key in [('slope', 'slope'), ('intercept', 'intercept'), ('rSquared', 'r2'),
                     ('slopeStdErr', 'stderr'), ('diffusionCoefficient', 'diffusion'),
                     ('diffusionStdErr', 'diffusionErr')]:
        assert regression[got] == approx(expected[key])
    for axis in ('x', 'y', 'z'):
        assert regression['axisDiffusion'][axis] == approx(expected[axis])


def reorder_definition(text: str) -> str:
    prefix, shards, current = [], [], None
    for line in text.splitlines():
        if line.startswith('@@SHARD|'):
            if current is not None:
                shards.append(current)
            current = [line]
        elif current is not None:
            if line == '@@END_SHARD':
                current.append(line)
                shards.append(current)
                current = None
            else:
                current.append(line)
        else:
            prefix.append(line)
    if current is not None:
        shards.append(current)
    out = prefix[:]
    for shard in reversed(shards):
        closed = shard[-1] == '@@END_SHARD'
        body = shard[1:-1] if closed else shard[1:]
        out.append(shard[0])
        out.extend(reversed(body))
        if closed:
            out.append('@@END_SHARD')
    return '\n'.join(out) + '\n'


def test_bundled_analyze_checkpoint_database_and_report(tmp_path):
    """The bundled experiment couples canonical checkpoint bytes, report digests, and all persisted scientific rows."""
    text = (FIXTURES / 'brownian.def').read_text()
    ref = reference(text)
    proc, state, db, report = run_mode(tmp_path, 'analyze', text=text, name='bundled')
    assert proc.returncode == 0 and proc.stdout.encode() == report.read_bytes()
    assert state.read_text() == ref['state']['stateText']
    parsed = json.loads(report.read_text())
    assert_report(parsed, ref)
    manifest = query(db, 'SELECT * FROM analysis_manifest')
    assert manifest == [[
        'brownian-diffusion-report/v2', ref['state']['sourceSha256'],
        ref['state']['stateSha256'], ref['datasetSha256'],
        str(len(ref['complete'])), str(len(ref['rejected']))
    ]]
    records = query(db, 'SELECT tick,particle_id,x,y,z,generation,shard_id FROM recovered_records ORDER BY tick,particle_id')
    assert len(records) == len(ref['selected'])


def test_dynamic_fresh_experiments_change_all_digest_links(tmp_path):
    """Fresh particle IDs and coordinates must propagate through checkpoint, report, database, and three independent digests."""
    outputs = []
    for seed in (17, 29):
        _, text, particles = dynamic_experiment(seed, f'{tmp_path.name}-{seed}')
        ref = reference(text)
        proc, _, db, report = run_mode(tmp_path, 'analyze', text=text, name=f'dyn{seed}')
        assert proc.returncode == 0
        parsed = json.loads(report.read_text())
        assert parsed['simulation']['particles'] == list(particles)
        assert_report(parsed, ref)
        assert query(db, 'SELECT DISTINCT particle_id FROM recovered_records ORDER BY particle_id') == [[p] for p in sorted(particles)]
        outputs.append((parsed['sourceSha256'], parsed['stateSha256'], parsed['datasetSha256'], parsed['regression']['diffusionCoefficient']))
    assert len(set(outputs)) == 2


def test_periodic_unwrap_drift_and_msd_tables_are_coupled(tmp_path):
    """Periodic crossings and ensemble drift must be reflected consistently in trajectories, MSD rows, and regression."""
    _, text, _ = dynamic_experiment(41, tmp_path.name + '-drift')
    ref = reference(text)
    proc, _, db, report = run_mode(tmp_path, 'analyze', text=text, name='drift')
    assert proc.returncode == 0
    points = query(db, 'SELECT segment_id,tick,particle_id,ux,uy,uz,drift_x,drift_y,drift_z FROM trajectory_points ORDER BY segment_id,tick,particle_id')
    expected_points = sorted(ref['points'], key=lambda row: (row[0], row[1], row[2]))
    assert len(points) == len(expected_points)
    for got, expected in zip(points, expected_points):
        assert [int(got[0]), int(got[1]), got[2]] == [expected[0], expected[1], expected[2]]
        for index in range(6):
            assert float(got[3 + index]) == approx(expected[6 + index])
    assert_report(json.loads(report.read_text()), ref)


def test_generation_conflict_repair_duplicate_and_incomplete_precedence(tmp_path):
    """A later repair simultaneously supersedes an old conflict, fills a missing particle, and deduplicates equal rows."""
    initial, extended, _ = dynamic_experiment(53, tmp_path.name + '-precedence')
    initial_ref, extended_ref = reference(initial), reference(extended)
    assert initial_ref['counts']['conflictingKeys'] == 1
    assert any(item['reason'] == 'missing-particle' for item in initial_ref['rejected'])
    assert extended_ref['counts']['supersededDiscarded'] >= 2
    assert extended_ref['counts']['duplicatesDiscarded'] == 1
    proc, _, _, report = run_mode(tmp_path, 'analyze', text=extended, name='precedence')
    assert proc.returncode == 0
    assert_report(json.loads(report.read_text()), extended_ref)


def test_analyze_resume_and_rebuild_are_byte_and_digest_equivalent(tmp_path):
    """A resumed higher-generation experiment must change checkpoint science, while rebuild reproduces it byte-for-byte."""
    initial, extended, _ = dynamic_experiment(67, tmp_path.name + '-resume')
    state = tmp_path / 'lab.state'
    db = tmp_path / 'lab.duckdb'
    report = tmp_path / 'lab.json'
    p1, _, _, _ = run_mode(tmp_path, 'analyze', text=initial, name='initial', state=state, db=db, report=report)
    assert p1.returncode == 0
    first = json.loads(report.read_text())
    first_state = state.read_bytes()
    p2, _, _, _ = run_mode(tmp_path, 'resume', text=extended, name='extended', state=state, db=db, report=report)
    assert p2.returncode == 0
    resumed_bytes = report.read_bytes()
    resumed = json.loads(resumed_bytes)
    assert state.read_bytes() != first_state
    assert (resumed['sourceSha256'], resumed['stateSha256'], resumed['datasetSha256']) != (first['sourceSha256'], first['stateSha256'], first['datasetSha256'])
    rebuild_db, rebuild_report = tmp_path / 'rebuilt.duckdb', tmp_path / 'rebuilt.json'
    p3, _, _, _ = run_mode(tmp_path, 'rebuild', name='rebuilt', state=state, db=rebuild_db, report=rebuild_report)
    assert p3.returncode == 0 and p3.stdout.encode() == resumed_bytes == rebuild_report.read_bytes()
    for sql in (
        'SELECT * FROM source_shards ORDER BY generation,shard_id',
        'SELECT * FROM recovered_records ORDER BY tick,particle_id',
        'SELECT * FROM trajectory_points ORDER BY segment_id,tick,particle_id',
        'SELECT * FROM rejected_timesteps ORDER BY tick',
        'SELECT * FROM msd_by_lag ORDER BY lag',
        'SELECT * FROM analysis_manifest',
    ):
        assert query(db, sql) == query(rebuild_db, sql)


def test_resume_rejects_changed_missing_and_metadata_prior_state_atomically(tmp_path):
    """Resume rejects every incompatible prefix without changing the valid checkpoint, database, or report."""
    initial, extended, _ = dynamic_experiment(71, tmp_path.name + '-immutable')
    state, db, report = tmp_path / 'keep.state', tmp_path / 'keep.duckdb', tmp_path / 'keep.json'
    p, _, _, _ = run_mode(tmp_path, 'analyze', text=initial, name='seed', state=state, db=db, report=report)
    assert p.returncode == 0
    expected = (state.read_bytes(), db.read_bytes(), report.read_bytes())
    changed_lines = extended.splitlines()
    for line_index, line in enumerate(changed_lines):
        if line.startswith('R|'):
            changed_lines[line_index] = line + '0'
            break
    changed = '\n'.join(changed_lines) + '\n'
    missing_lines = []
    skipping = False
    for line in extended.splitlines():
        if line.startswith('@@SHARD|id=base_'):
            skipping = True
            continue
        if skipping and line == '@@END_SHARD':
            skipping = False
            continue
        if not skipping:
            missing_lines.append(line)
    missing = '\n'.join(missing_lines) + '\n'
    changed_meta = extended.replace('dt=0.2', 'dt=0.25', 1)
    for index, bad in enumerate((changed, missing, changed_meta)):
        proc, _, _, _ = run_mode(tmp_path, 'resume', text=bad, name=f'bad{index}', state=state, db=db, report=report)
        assert proc.returncode == 4
        assert (state.read_bytes(), db.read_bytes(), report.read_bytes()) == expected


def test_tampered_noncanonical_and_missing_checkpoints_exit4_and_preserve_outputs(tmp_path):
    """Rebuild validates checkpoint hashes, canonical ordering, and presence before touching output artifacts."""
    _, extended, _ = dynamic_experiment(73, tmp_path.name + '-tamper')
    proc, state, _, _ = run_mode(tmp_path, 'analyze', text=extended, name='source')
    assert proc.returncode == 0
    valid = state.read_text()
    variants = [
        valid.replace('stateSha256|', 'stateSha256|0', 1),
        valid.replace('record|', 'record|A', 1),
        '\n'.join(reversed(valid.rstrip('\n').splitlines())) + '\n',
    ]
    for index, content in enumerate(variants):
        bad_state = tmp_path / f'tampered{index}.state'
        bad_state.write_text(content)
        db, report = tmp_path / f'keep{index}.db', tmp_path / f'keep{index}.json'
        db.write_bytes(b'DB-SENTINEL')
        report.write_text('REPORT-SENTINEL')
        p, _, _, _ = run_mode(tmp_path, 'rebuild', name=f't{index}', state=bad_state, db=db, report=report)
        assert p.returncode == 4 and db.read_bytes() == b'DB-SENTINEL' and report.read_text() == 'REPORT-SENTINEL'
    missing = tmp_path / 'missing.state'
    p, _, _, _ = run_mode(tmp_path, 'rebuild', name='missing', state=missing,
                           db=tmp_path / 'missing.db', report=tmp_path / 'missing.json')
    assert p.returncode == 4


def test_equivalent_shard_and_row_order_is_checkpoint_and_report_identical(tmp_path):
    """Equivalent definitions canonicalize to identical checkpoints, reports, and source-shard database rows."""
    _, text, _ = dynamic_experiment(79, tmp_path.name + '-order')
    reordered = reorder_definition(text)
    p1, s1, d1, r1 = run_mode(tmp_path, 'analyze', text=text, name='order1')
    p2, s2, d2, r2 = run_mode(tmp_path, 'analyze', text=reordered, name='order2')
    assert p1.returncode == p2.returncode == 0
    assert s1.read_bytes() == s2.read_bytes() and r1.read_bytes() == r2.read_bytes()
    assert query(d1, 'SELECT * FROM source_shards ORDER BY generation,shard_id') == query(d2, 'SELECT * FROM source_shards ORDER BY generation,shard_id')
    assert query(d1, 'SELECT * FROM recovered_records ORDER BY tick,particle_id') == query(d2, 'SELECT * FROM recovered_records ORDER BY tick,particle_id')


def test_exact_six_table_schema_and_manifest_digest_links(tmp_path):
    """Every table name, column type, digest link, and manifest count is exact."""
    _, text, _ = dynamic_experiment(83, tmp_path.name + '-schema')
    ref = reference(text)
    proc, state, db, report = run_mode(tmp_path, 'analyze', text=text, name='schema')
    assert proc.returncode == 0
    expected = {
        'source_shards': [('shard_id', 'VARCHAR'), ('generation', 'BIGINT'), ('records', 'BIGINT'), ('shard_sha256', 'VARCHAR')],
        'recovered_records': [('tick', 'BIGINT'), ('particle_id', 'VARCHAR'), ('x', 'DOUBLE'), ('y', 'DOUBLE'), ('z', 'DOUBLE'), ('generation', 'BIGINT'), ('shard_id', 'VARCHAR')],
        'trajectory_points': [('segment_id', 'BIGINT'), ('tick', 'BIGINT'), ('particle_id', 'VARCHAR'), ('x', 'DOUBLE'), ('y', 'DOUBLE'), ('z', 'DOUBLE'), ('ux', 'DOUBLE'), ('uy', 'DOUBLE'), ('uz', 'DOUBLE'), ('drift_x', 'DOUBLE'), ('drift_y', 'DOUBLE'), ('drift_z', 'DOUBLE')],
        'rejected_timesteps': [('tick', 'BIGINT'), ('reason', 'VARCHAR')],
        'msd_by_lag': [('lag', 'BIGINT'), ('time', 'DOUBLE'), ('pairs', 'BIGINT'), ('msd_x', 'DOUBLE'), ('msd_y', 'DOUBLE'), ('msd_z', 'DOUBLE'), ('msd_total', 'DOUBLE')],
        'analysis_manifest': [('schema', 'VARCHAR'), ('source_sha256', 'VARCHAR'), ('state_sha256', 'VARCHAR'), ('dataset_sha256', 'VARCHAR'), ('complete_timesteps', 'BIGINT'), ('rejected_timesteps', 'BIGINT')],
    }
    tables = query(db, "SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY table_name")
    assert [row[0] for row in tables] == sorted(expected)
    for table, columns in expected.items():
        got = query(db, f"SELECT column_name,data_type FROM information_schema.columns WHERE table_name='{table}' ORDER BY ordinal_position")
        assert [tuple(row) for row in got] == columns
    parsed = json.loads(report.read_text())
    assert parsed['stateSha256'] in state.read_text()
    assert_report(parsed, ref)


def test_invalid_insufficient_and_aliased_paths_preserve_managed_artifacts(tmp_path):
    """Validation, scientific insufficiency, and path alias errors use distinct exits without partial replacement."""
    state, db, report = tmp_path / 'keep.state', tmp_path / 'keep.db', tmp_path / 'keep.json'
    for path, content in ((state, b'STATE'), (db, b'DB'), (report, b'REPORT')):
        path.write_bytes(content)
    bad = '@@META|dt=-1|dimensions=3|box=10|particles=a,b|fit=1:3\n@@SHARD|id=x|generation=0\n'
    p, _, _, _ = run_mode(tmp_path, 'analyze', text=bad, name='invalid', state=state, db=db, report=report)
    assert p.returncode == 2 and (state.read_bytes(), db.read_bytes(), report.read_bytes()) == (b'STATE', b'DB', b'REPORT')
    rows = [record(tick, particle, (index + tick * .1, index + tick * .2, index + tick * .3))
            for tick in range(3) for index, particle in enumerate(('a', 'b', 'c'))]
    insufficient = make_definition(particles=('a', 'b', 'c'), fit=(1, 4), shards=[('s', 0, rows, True)])
    p, _, _, _ = run_mode(tmp_path, 'analyze', text=insufficient, name='insufficient', state=state, db=db, report=report)
    assert p.returncode == 3 and (state.read_bytes(), db.read_bytes(), report.read_bytes()) == (b'STATE', b'DB', b'REPORT')
    _, valid, _ = dynamic_experiment(89, tmp_path.name + '-alias')
    p, _, _, _ = run_mode(tmp_path, 'analyze', text=valid, name='alias', state=state, db=state, report=report)
    assert p.returncode == 2 and state.read_bytes() == b'STATE' and report.read_bytes() == b'REPORT'


def test_publication_failure_restores_checkpoint_database_and_report(tmp_path):
    """A failure to publish one requested artifact must preserve all three previously valid targets."""
    _, text, _ = dynamic_experiment(97, tmp_path.name + '-publish')
    state, db = tmp_path / 'published.state', tmp_path / 'published.db'
    report_dir = tmp_path / 'report-directory'
    state.write_bytes(b'STATE-SENTINEL')
    db.write_bytes(b'DB-SENTINEL')
    report_dir.mkdir()
    proc, _, _, _ = run_mode(tmp_path, 'analyze', text=text, name='publish', state=state, db=db, report=report_dir)
    assert proc.returncode == 5
    assert state.read_bytes() == b'STATE-SENTINEL' and db.read_bytes() == b'DB-SENTINEL' and report_dir.is_dir()
    assert not list(tmp_path.glob('.*.tmp'))


def test_report_format_help_rerun_and_idempotent_resume(tmp_path):
    """Canonical number rendering, help, repeated analyze, and resume-without-new-shards are deterministic."""
    help_proc = subprocess.run([str(RUN), '--help'], text=True, capture_output=True)
    assert help_proc.returncode == 0 and 'analyze' in help_proc.stdout and 'rebuild' in help_proc.stdout
    _, text, _ = dynamic_experiment(101, tmp_path.name + '-format')
    p1, s1, d1, r1 = run_mode(tmp_path, 'analyze', text=text, name='fmt1')
    p2, s2, _, r2 = run_mode(tmp_path, 'analyze', text=text, name='fmt2')
    assert p1.returncode == p2.returncode == 0 and s1.read_bytes() == s2.read_bytes() and r1.read_bytes() == r2.read_bytes()
    before = (s1.read_bytes(), r1.read_bytes())
    p3, _, _, _ = run_mode(tmp_path, 'resume', text=text, name='same', state=s1, db=d1, report=r1)
    assert p3.returncode == 0 and (s1.read_bytes(), r1.read_bytes()) == before
    raw = r1.read_text()
    assert raw.endswith('\n') and not raw.endswith('\n\n') and 'e-' not in raw.lower() and 'e+' not in raw.lower()
    assert '-0.000000000' not in raw
    decimals = re.findall(r':(-?\d+\.\d+)(?=[,}])', raw)
    assert decimals and all(len(token.rsplit('.', 1)[1]) == 9 for token in decimals)
    parsed = json.loads(raw)
    assert isinstance(parsed['simulation']['dimensions'], int)
    assert all(isinstance(item['records'], int) for item in parsed['recovery']['shardsApplied'])
    assert all(isinstance(item['pairs'], int) for item in parsed['msd'])
