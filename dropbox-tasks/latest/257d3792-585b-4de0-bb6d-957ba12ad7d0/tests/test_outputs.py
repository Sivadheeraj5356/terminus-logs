"""Verifier for the Dart spreadsheet formula engine task."""

from pathlib import Path
import json
import shutil
import subprocess

import pytest
from sheetref import STAGES, solve

APP = Path('/app')
DATA = APP / 'data/workbook.json'
OUT = APP / 'output'
SRC = APP / 'src'


def _mk_hidden_case(i):
    sheet = 'S'
    n = (i % 6) + 4
    rng = f'A1:A{n}'
    cells = {f'A{r}': r for r in range(1, n + 1)}
    names = {f'R{i}': f'{sheet}!{rng}', f'Tail{i}': f'{sheet}!A2:A{n}'}
    mode = i % 10
    if mode == 0:
        cells['A1'] = '=B1+1'
        cells['B1'] = '=C1+1'
        cells['C1'] = '=A1+1'
    elif mode == 1:
        cells['B1'] = '=A1/0'
        cells['C1'] = '=B1+1'
    elif mode == 2:
        cells['A3'] = 'bad'
        cells['B1'] = '=A3+1'
        cells['C1'] = '=B1'
    elif mode == 3:
        cells['B1'] = f'=SUM({rng})'
        cells['C1'] = f'=MAX(R{i})'
        cells['D1'] = '=B1+C1'
    elif mode == 4:
        cells['B1'] = f'=MIN(Tail{i})'
        cells['C1'] = f'=COUNT(R{i})'
        cells['D1'] = '=B1*C1'
    elif mode == 5:
        cells['B1'] = f'=SUM({sheet}!{rng})'
        cells['C1'] = '=IF(B1>0,B1,0)'
    elif mode == 6:
        cells['B1'] = f'=MAX(R{i})-MIN(R{i})'
        cells['C1'] = '=B1+COUNT(A1:A2)'
    elif mode == 7:
        cells['B1'] = '=A1+A2*A3'
        cells['C1'] = '=B1-A4'
    elif mode == 8:
        cells['B1'] = '=IF(A1>=1,SUM(A1:A2),0)'
        cells['C1'] = '=B1/2'
    else:
        cells['B1'] = f'=SUM(R{i})'
        cells['C1'] = f'=SUM(Tail{i})'
        cells['D1'] = '=B1-C1'
    edits = [{'id': f'e{i}', 'cell': f'{sheet}!A1', 'value': n + i}]
    if mode in {1, 2}:
        edits.append({'id': f'f{i}', 'cell': f'{sheet}!B1', 'value': '=A2+1'})
    if i % 13 == 0:
        cells['X1'] = '=SUM(S!A1:A3)'
        cells['Y1'] = f'=SUM(Tail{i})'
    return {'sheets': [{'name': sheet, 'cells': cells}], 'names': names, 'edits': edits}


PRIMARY_STAGES = STAGES
HIDDEN_CASE_IDS = [i for i in range(50) if i % 10 not in {0, 8}]
HIDDEN_CASES = [_mk_hidden_case(i) for i in HIDDEN_CASE_IDS]
PRIMARY_WORKBOOK = json.loads(DATA.read_text())


def _mk_brutal_case(i):
    rows = 5 + (i % 5)
    main_cells = {f'A{r}': (i + r * 3) for r in range(1, rows + 1)}
    aux_cells = {f'A{r}': f'=Main!A{r}+{i % 7}' for r in range(1, rows + 1)}
    calc_cells = {
        'A1': '=SUM(MainBlock)+SUM(AuxBlock)',
        'A2': '=MAX(AuxBlock)-MIN(MainBlock)',
        'A3': '=COUNT(MainBlock)+COUNT(AuxBlock)',
        'A4': '=IF(A1>A2,A1-A2,A2-A1)',
        'B1': '=A1+A2*A3',
        'B2': '=SUM(Calc!A1:B1)',
        'C1': '=B2/0' if i % 4 == 0 else '=B2-COUNT(TailBlock)',
        'D1': '=MissingName+1',
    }
    if i % 3 == 0:
        calc_cells['E1'] = '=E2+1'
        calc_cells['E2'] = '=E1+1'
    if i % 5 == 0:
        aux_cells['B1'] = 'text'
        calc_cells['F1'] = '=Aux!B1+1'

    edits = [
        {'id': f'b{i}_main', 'cell': 'Main!A1', 'value': rows + i},
        {'id': f'b{i}_new_formula', 'cell': 'Calc!Z1', 'value': '=SUM(MainBlock)+COUNT(AuxBlock)'},
    ]
    if i % 2 == 0:
        edits.append({'id': f'b{i}_fix_div', 'cell': 'Calc!C1', 'value': '=B2/2'})
    if i % 7 == 0:
        edits.append({'id': f'b{i}_self', 'cell': 'Aux!Z9', 'value': '=Aux!Z9+1'})

    return {
        'sheets': [
            {'name': 'Main', 'cells': main_cells},
            {'name': 'Aux', 'cells': aux_cells},
            {'name': 'Calc', 'cells': calc_cells},
        ],
        'names': {
            'MainBlock': f'Main!A1:A{rows}',
            'AuxBlock': f'Aux!A1:A{rows}',
            'TailBlock': f'Main!A2:A{rows}',
            'CalcBand': 'Calc!A1:B2',
        },
        'edits': edits,
    }


BRUTAL_CASE_IDS = [i for i in range(50) if i % 2 == 1]
BRUTAL_CASES = [_mk_brutal_case(i) for i in BRUTAL_CASE_IDS]


def load(stage):
    return json.loads((OUT / f'{stage}.json').read_text())


def run_solver(workbook):
    DATA.write_text(json.dumps(workbook, separators=(',', ':')) + '\n')
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    sources = sorted(SRC.glob('*.dart'))
    assert sources, 'missing Dart source under /app/src'
    entrypoint = SRC / 'main.dart'
    assert entrypoint.exists(), 'required Dart entrypoint /app/src/main.dart is missing'
    subprocess.run(['dart', str(entrypoint), str(DATA), str(OUT)], check=True, timeout=30)


def run_solver_paths(workbook, input_path, output_dir):
    input_path.write_text(json.dumps(workbook, separators=(',', ':')) + '\n')
    output_dir.mkdir(parents=True, exist_ok=True)
    for stage in STAGES:
        (output_dir / f'{stage}.json').write_text('{"stale":true}\n')
    sources = sorted(SRC.glob('*.dart'))
    assert sources, 'missing Dart source under /app/src'
    entrypoint = SRC / 'main.dart'
    assert entrypoint.exists(), 'required Dart entrypoint /app/src/main.dart is missing'
    subprocess.run(['dart', str(entrypoint), str(input_path), str(output_dir)], check=True, timeout=30)
    return {stage: json.loads((output_dir / f'{stage}.json').read_text()) for stage in STAGES}


def assert_output_contract(got):
    assert set(got) == set(STAGES)
    assert set(got['parse']) == {'sheets', 'cells', 'formulas', 'names', 'edits'}
    assert set(got['formulas']) == {'formulas'}
    assert set(got['deps']) == {'deps'}
    assert set(got['order']) == {'order', 'cycles'}
    assert set(got['values']) == {'values'}
    assert set(got['errors']) == {'errors'}
    assert set(got['recalculation']) == {'edits'}
    assert set(got['lineage']) == {'lineage'}
    assert set(got['audit']) == {'audit'}
    assert set(got['metrics']) == {
        'max_direct_dependencies',
        'max_transitive_dependencies',
        'numeric_formula_sum',
        'text_formula_count',
        'checksum',
    }
    assert set(got['summary']) == {'formulas', 'dependencies', 'cycles', 'errors', 'edits', 'lineage_edges'}
    assert [row['cell'] for row in got['formulas']['formulas']] == sorted(row['cell'] for row in got['formulas']['formulas'])
    assert [row['cell'] for row in got['deps']['deps']] == sorted(row['cell'] for row in got['deps']['deps'])
    assert [row['cell'] for row in got['lineage']['lineage']] == sorted(row['cell'] for row in got['lineage']['lineage'])
    assert [row['cell'] for row in got['audit']['audit']] == sorted(row['cell'] for row in got['audit']['audit'])


def test_source_is_dart_only():
    srcs = sorted(SRC.glob('*.dart'))
    assert srcs, 'missing Dart source under /app/src'
    assert (SRC / 'main.dart').exists(), 'required Dart entrypoint /app/src/main.dart is missing'
    src = '\n'.join(p.read_text() for p in srcs)
    assert 'dart:convert' in src
    banned = ['Process.run', 'Process.start', 'python', 'sheetref', 'base64Decode']
    assert not any(x in src for x in banned)
    assert not list(SRC.glob('*.py'))
    assert 'Main!A3' not in src


@pytest.mark.parametrize('stage', PRIMARY_STAGES)
def test_primary_stage_matches(stage):
    run_solver(PRIMARY_WORKBOOK)
    assert load(stage) == solve(DATA)[stage]


def test_missing_input_fails():
    sources = sorted(SRC.glob('*.dart'))
    assert sources
    entrypoint = SRC / 'main.dart'
    assert entrypoint.exists(), 'required Dart entrypoint /app/src/main.dart is missing'
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run(['dart', str(entrypoint), '/tmp/no_such_workbook.json', str(OUT)], check=True, timeout=30)


def test_determinism_repeated_hidden_case():
    wb = _mk_hidden_case(37)
    run_solver(wb)
    first = {stage: (OUT / f'{stage}.json').read_bytes() for stage in STAGES}
    run_solver(wb)
    second = {stage: (OUT / f'{stage}.json').read_bytes() for stage in STAGES}
    assert first == second


@pytest.mark.parametrize('workbook', HIDDEN_CASES, ids=lambda wb: json.dumps(wb, sort_keys=True)[:24])
def test_hidden_full_pipeline_matches(workbook):
    run_solver(workbook)
    want = solve(DATA)
    for stage in STAGES:
        assert load(stage) == want[stage]


@pytest.mark.parametrize('workbook', HIDDEN_CASES[:20], ids=lambda wb: json.dumps(wb, sort_keys=True)[:24])
def test_hidden_output_contracts(workbook):
    run_solver(workbook)
    got = {stage: load(stage) for stage in STAGES}
    assert_output_contract(got)
    assert got['summary']['formulas'] == len(got['formulas']['formulas'])
    assert got['summary']['errors'] == len(got['errors']['errors'])
    assert got['summary']['lineage_edges'] == sum(len(row['transitive']) for row in got['lineage']['lineage'])


@pytest.mark.parametrize('workbook', BRUTAL_CASES, ids=lambda wb: json.dumps(wb, sort_keys=True)[:24])
def test_brutal_full_pipeline_matches(workbook):
    run_solver(workbook)
    want = solve(DATA)
    for stage in STAGES:
        assert load(stage) == want[stage]


@pytest.mark.parametrize('workbook', BRUTAL_CASES[:20], ids=lambda wb: json.dumps(wb, sort_keys=True)[:24])
def test_brutal_contracts_and_pressure(workbook):
    run_solver(workbook)
    got = {stage: load(stage) for stage in STAGES}
    assert_output_contract(got)
    assert got['parse']['sheets'] == 3
    assert got['parse']['names'] == 4
    assert any(row['state'] in {'cycle', 'error'} for row in got['audit']['audit'])
    assert got['metrics']['max_direct_dependencies'] >= 1
    assert got['metrics']['max_transitive_dependencies'] >= 1
    assert got['summary']['dependencies'] == sum(len(row['depends_on']) for row in got['deps']['deps'])


@pytest.mark.parametrize('workbook', BRUTAL_CASES[:10], ids=lambda wb: json.dumps(wb, sort_keys=True)[:24])
def test_brutal_custom_paths_and_stale_outputs(workbook, tmp_path):
    got = run_solver_paths(workbook, tmp_path / 'book.json', tmp_path / 'out')
    input_copy = tmp_path / 'book.json'
    want = solve(input_copy)
    for stage in STAGES:
        assert got[stage] == want[stage]
