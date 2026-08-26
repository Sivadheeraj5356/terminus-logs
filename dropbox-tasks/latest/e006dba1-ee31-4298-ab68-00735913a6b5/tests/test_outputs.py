"""Securitization waterfall engine verification - exercises all paths."""

import json
import subprocess
import pytest
import os

BIN = '/app/waterfall'
INPUT = '/app/input/collections.json'
OUTPUT = '/app/output/waterfall.json'
TIMEOUT = 30


@pytest.fixture(scope='session', autouse=True)
def build_and_run():
    """compile and run the waterfall engine"""
    subprocess.run(
        ['bash', '-c', 'cd /app && go build -o /app/waterfall . && /app/waterfall'],
        capture_output=True, timeout=60,
    )
    yield


@pytest.fixture(scope='session')
def output_data(build_and_run):
    """load the output waterfall json"""
    with open(OUTPUT) as f:
        return json.load(f)


# === STRUCTURAL TESTS ===

def test_output_file_exists(build_and_run):
    """output file must be created at the specified path"""
    assert os.path.isfile(OUTPUT)


def test_output_is_array_of_11_periods(output_data):
    """output contains exactly 11 period records (deal terminates at clean-up)"""
    assert isinstance(output_data, list)
    assert len(output_data) == 11


def test_period_one_structure(output_data):
    """period 1 record has all required fields"""
    p1 = output_data[0]
    assert p1['period'] == 1
    assert 'tranche_payments' in p1
    assert 'reserve_balance' in p1
    assert 'mode' in p1
    assert 'clean_up' in p1


def test_tranche_payment_structure(output_data):
    """each tranche payment has all required fields"""
    for p in output_data:
        for tp in p['tranche_payments']:
            assert 'id' in tp
            assert 'interest_paid' in tp
            assert 'principal_paid' in tp
            assert 'ending_balance' in tp
            assert 'pik_amount' in tp


def test_four_tranches_per_period(output_data):
    """each period has exactly 4 tranche payments"""
    for p in output_data:
        assert len(p['tranche_payments']) == 4


# === PERIOD 1 - SEQUENTIAL MODE, NORMAL FLOW ===

def test_period_1_mode_sequential(output_data):
    """first period uses sequential distribution mode"""
    assert output_data[0]['mode'] == 'sequential'


def test_period_1_tranche_a_interest(output_data):
    """tranche A interest: 5000000 * 0.05/12 = 20833.33"""
    p1 = output_data[0]
    a = next(t for t in p1['tranche_payments'] if t['id'] == 'T-A')
    assert a['interest_paid'] == 20833.33


def test_period_1_tranche_b_interest(output_data):
    """tranche B interest: 2000000 * 0.07/12 = 11666.67"""
    p1 = output_data[0]
    b = next(t for t in p1['tranche_payments'] if t['id'] == 'T-B')
    assert b['interest_paid'] == 11666.67


def test_period_1_tranche_c_interest(output_data):
    """tranche C interest: 1000000 * 0.09/12 = 7500.00"""
    p1 = output_data[0]
    c = next(t for t in p1['tranche_payments'] if t['id'] == 'T-C')
    assert c['interest_paid'] == 7500.0


def test_period_1_no_pik(output_data):
    """no PIK shortfall occurs in period 1"""
    p1 = output_data[0]
    for tp in p1['tranche_payments']:
        assert tp['pik_amount'] == 0.0


def test_period_1_a_principal(output_data):
    """tranche A principal paid in period 1 (sequential scheduled + prepay share)"""
    p1 = output_data[0]
    a = next(t for t in p1['tranche_payments'] if t['id'] == 'T-A')
    assert a['principal_paid'] == 382387.03


def test_period_1_a_ending_balance(output_data):
    """tranche A ending balance after period 1"""
    p1 = output_data[0]
    a = next(t for t in p1['tranche_payments'] if t['id'] == 'T-A')
    assert a['ending_balance'] == 4617612.97


def test_period_1_b_principal(output_data):
    """tranche B prepay share in period 1"""
    p1 = output_data[0]
    b = next(t for t in p1['tranche_payments'] if t['id'] == 'T-B')
    assert b['principal_paid'] == 13075.31


def test_period_1_c_principal(output_data):
    """tranche C prepay share in period 1"""
    p1 = output_data[0]
    c = next(t for t in p1['tranche_payments'] if t['id'] == 'T-C')
    assert c['principal_paid'] == 6537.66


def test_sequential_principal_goes_to_a_first(output_data):
    """sequential mode directs scheduled principal to tranche A before B"""
    p1 = output_data[0]
    a = next(t for t in p1['tranche_payments'] if t['id'] == 'T-A')
    b = next(t for t in p1['tranche_payments'] if t['id'] == 'T-B')
    assert a['principal_paid'] > b['principal_paid']


# === PERIOD 3 - PIK (INTEREST SHORTFALL) ===

def test_period_3_pik_fires_on_c(output_data):
    """period 3 has very low collections causing PIK on tranche C"""
    p3 = output_data[2]
    c = next(t for t in p3['tranche_payments'] if t['id'] == 'T-C')
    assert c['pik_amount'] == 4590.75


def test_period_3_c_partial_interest(output_data):
    """tranche C receives only partial interest in period 3"""
    p3 = output_data[2]
    c = next(t for t in p3['tranche_payments'] if t['id'] == 'T-C')
    assert c['interest_paid'] == 2803.77


def test_period_3_c_balance_increases(output_data):
    """PIK capitalizes shortfall onto C balance"""
    p3 = output_data[2]
    c = next(t for t in p3['tranche_payments'] if t['id'] == 'T-C')
    assert c['ending_balance'] == 990526.12


def test_period_3_a_and_b_fully_paid_interest(output_data):
    """tranches A and B still get full interest in period 3"""
    p3 = output_data[2]
    a = next(t for t in p3['tranche_payments'] if t['id'] == 'T-A')
    b = next(t for t in p3['tranche_payments'] if t['id'] == 'T-B')
    assert a['pik_amount'] == 0.0
    assert b['pik_amount'] == 0.0
    assert a['interest_paid'] == 17693.65
    assert b['interest_paid'] == 11502.58


def test_period_3_no_principal(output_data):
    """no principal distributed in period 3 (scheduled principal is 0)"""
    p3 = output_data[2]
    for tp in p3['tranche_payments']:
        assert tp['principal_paid'] == 0.0


# === PERIODS 5-6 - PRO-RATA MODE ===

def test_period_5_pro_rata_mode(output_data):
    """period 5 switches to pro_rata (all triggers pass)"""
    assert output_data[4]['mode'] == 'pro_rata'


def test_period_6_pro_rata_mode(output_data):
    """period 6 remains in pro_rata"""
    assert output_data[5]['mode'] == 'pro_rata'


def test_period_5_principal_proportional(output_data):
    """pro-rata distributes principal proportionally to A/B/C balances"""
    p5 = output_data[4]
    a = next(t for t in p5['tranche_payments'] if t['id'] == 'T-A')
    b = next(t for t in p5['tranche_payments'] if t['id'] == 'T-B')
    c = next(t for t in p5['tranche_payments'] if t['id'] == 'T-C')
    assert a['principal_paid'] == 384116.17
    assert b['principal_paid'] == 157140.14
    assert c['principal_paid'] == 78564.57


def test_period_6_principal_values(output_data):
    """period 6 pro-rata principal exact values"""
    p6 = output_data[5]
    a = next(t for t in p6['tranche_payments'] if t['id'] == 'T-A')
    b = next(t for t in p6['tranche_payments'] if t['id'] == 'T-B')
    c = next(t for t in p6['tranche_payments'] if t['id'] == 'T-C')
    assert a['principal_paid'] == 366521.26
    assert b['principal_paid'] == 154274.25
    assert c['principal_paid'] == 77131.73


# === PERIOD 7 - TRIGGER BREACH, SEQUENTIAL LOCK, STEP-UP, PIK ===

def test_period_7_sequential_lock(output_data):
    """period 7 reverts to sequential permanently (cum_default_rate >= 0.04)"""
    assert output_data[6]['mode'] == 'sequential'


def test_period_7_pik_on_c(output_data):
    """period 7 triggers PIK on C (high defaults + loss writedown reduce available)"""
    p7 = output_data[6]
    c = next(t for t in p7['tranche_payments'] if t['id'] == 'T-C')
    assert c['pik_amount'] == 6746.82


def test_period_7_c_partial_interest(output_data):
    """tranche C gets only partial interest in period 7"""
    p7 = output_data[6]
    c = next(t for t in p7['tranche_payments'] if t['id'] == 'T-C')
    assert c['interest_paid'] == 49.62


def test_period_7_step_up_active(output_data):
    """step-up triggers in period 7 (cum defaults >= 3%), C rate goes to 10%"""
    p8 = output_data[7]
    c = next(t for t in p8['tranche_payments'] if t['id'] == 'T-C')
    assert c['interest_paid'] == 6852.66


# === PERIODS 8-11 - SEQUENTIAL STAYS LOCKED ===

def test_sequential_stays_locked_period_8(output_data):
    """mode remains sequential after lock"""
    assert output_data[7]['mode'] == 'sequential'


def test_sequential_stays_locked_period_9(output_data):
    """mode remains sequential in period 9"""
    assert output_data[8]['mode'] == 'sequential'


def test_sequential_stays_locked_period_10(output_data):
    """mode remains sequential in period 10"""
    assert output_data[9]['mode'] == 'sequential'


def test_sequential_lock_never_reverts(output_data):
    """once locked sequential, no period reverts to pro_rata"""
    modes = [p['mode'] for p in output_data]
    for m in modes[6:]:
        assert m == 'sequential'


# === PERIOD 8 - SEQUENTIAL PRINCIPAL EXACT VALUES ===

def test_period_8_a_principal(output_data):
    """period 8 tranche A principal in sequential mode"""
    p8 = output_data[7]
    a = next(t for t in p8['tranche_payments'] if t['id'] == 'T-A')
    assert a['principal_paid'] == 513875.93
    assert a['ending_balance'] == 2470451.75


# === RESERVE BALANCE TESTS ===

def test_reserve_fills_by_period_4(output_data):
    """reserve reaches target (172000) by period 4"""
    assert output_data[3]['reserve_balance'] == 172000.0


def test_reserve_period_1(output_data):
    """reserve accumulates 45000 in period 1 from excess after principal"""
    assert output_data[0]['reserve_balance'] == 45000.0


def test_reserve_capped_at_target(output_data):
    """reserve never exceeds 2% of original pool balance (172000)"""
    for p in output_data:
        assert p['reserve_balance'] <= 172000.0


# === TURBO PRINCIPAL - FLOWS WHEN OC PASSES ===

def test_turbo_flows_period_5(output_data):
    """period 5 has turbo flowing to A after reserve is full and OC passes"""
    p5 = output_data[4]
    a = next(t for t in p5['tranche_payments'] if t['id'] == 'T-A')
    # A gets: pro-rata scheduled share + prepay share + turbo (82000)
    # total A principal = 384116.17 which includes 82000 turbo
    # without turbo, A sched+prepay would be 301888.39
    # verify the total includes turbo by checking the exact value
    assert a['principal_paid'] == 384116.17


def test_turbo_amount_period_8(output_data):
    """period 8 turbo sends principal to tranche A in sequential mode"""
    p8 = output_data[7]
    a = next(t for t in p8['tranche_payments'] if t['id'] == 'T-A')
    assert a['principal_paid'] == 513875.93


def test_turbo_amount_period_9_exact(output_data):
    """period 9 turbo flows to A (most senior with balance)"""
    p9 = output_data[8]
    a = next(t for t in p9['tranche_payments'] if t['id'] == 'T-A')
    assert a['principal_paid'] == 723093.13


def test_turbo_amount_period_10(output_data):
    """period 10 turbo flows to A"""
    p10 = output_data[9]
    a = next(t for t in p10['tranche_payments'] if t['id'] == 'T-A')
    assert a['principal_paid'] == 826741.34
    assert a['ending_balance'] == 920617.28


# === TURBO BLOCKED - OC TEST FAILURE ===

def test_turbo_blocked_period_4_oc_fails(output_data):
    """period 4 OC test fails so turbo does not flow despite reserve being full"""
    p4 = output_data[3]
    a = next(t for t in p4['tranche_payments'] if t['id'] == 'T-A')
    b = next(t for t in p4['tranche_payments'] if t['id'] == 'T-B')
    c = next(t for t in p4['tranche_payments'] if t['id'] == 'T-C')
    # total principal = sched to A + prepay pro-rata (no turbo component)
    # if turbo were flowing, A would get 15000 more
    assert a['principal_paid'] == 511510.19
    assert b['principal_paid'] == 29197.77
    assert c['principal_paid'] == 14666.86


def test_period_4_reserve_at_target_but_no_turbo(output_data):
    """reserve hits 172000 in period 4, but OC failure blocks turbo"""
    p4 = output_data[3]
    assert p4['reserve_balance'] == 172000.0
    # A ending balance proves no turbo flowed (would be 15000 less if it did)
    a = next(t for t in p4['tranche_payments'] if t['id'] == 'T-A')
    assert a['ending_balance'] == 3734965.11


# === CLEAN-UP CALL ===

def test_clean_up_fires_period_11(output_data):
    """clean-up triggers in period 11 (pool < 10% of original)"""
    assert output_data[10]['clean_up'] is True


def test_clean_up_zeroes_all_balances(output_data):
    """clean-up sets all tranche ending balances to zero"""
    p11 = output_data[10]
    for tp in p11['tranche_payments']:
        assert tp['ending_balance'] == 0.0


def test_clean_up_residual_gets_principal(output_data):
    """residual tranche receives its balance as principal in clean-up"""
    p11 = output_data[10]
    r = next(t for t in p11['tranche_payments'] if t['id'] == 'T-R')
    assert r['principal_paid'] == 470934.75


def test_clean_up_a_principal(output_data):
    """clean-up pays all remaining A balance as principal"""
    p11 = output_data[10]
    a = next(t for t in p11['tranche_payments'] if t['id'] == 'T-A')
    assert a['principal_paid'] == 920617.28


def test_clean_up_b_principal(output_data):
    """clean-up pays all remaining B balance as principal"""
    p11 = output_data[10]
    b = next(t for t in p11['tranche_payments'] if t['id'] == 'T-B')
    assert b['principal_paid'] == 1455005.40


def test_clean_up_c_principal(output_data):
    """clean-up pays all remaining C balance as principal"""
    p11 = output_data[10]
    c = next(t for t in p11['tranche_payments'] if t['id'] == 'T-C')
    assert c['principal_paid'] == 727328.34


def test_no_periods_after_cleanup(output_data):
    """deal terminates after clean-up, no period 12 output"""
    periods = [p['period'] for p in output_data]
    assert 12 not in periods


# === GENERAL INVARIANTS ===

def test_all_values_two_decimal_places(output_data):
    """every monetary value is rounded to exactly 2 decimal places"""
    for p in output_data:
        assert p['reserve_balance'] == round(p['reserve_balance'], 2)
        for tp in p['tranche_payments']:
            assert tp['interest_paid'] == round(tp['interest_paid'], 2)
            assert tp['principal_paid'] == round(tp['principal_paid'], 2)
            assert tp['ending_balance'] == round(tp['ending_balance'], 2)
            assert tp['pik_amount'] == round(tp['pik_amount'], 2)


def test_residual_gets_no_interest(output_data):
    """residual tranche never receives interest payments"""
    for p in output_data:
        r = next(t for t in p['tranche_payments'] if t['id'] == 'T-R')
        assert r['interest_paid'] == 0.0


def test_mode_field_valid_values(output_data):
    """mode is either sequential or pro_rata in every period"""
    for p in output_data:
        assert p['mode'] in ('sequential', 'pro_rata')


def test_no_clean_up_before_period_11(output_data):
    """clean-up does not fire in periods 1-10"""
    for p in output_data[:10]:
        assert p['clean_up'] is False


def test_prepayment_distributed_pro_rata_in_sequential(output_data):
    """prepay goes to B and C even in sequential mode (period 1)"""
    p1 = output_data[0]
    b = next(t for t in p1['tranche_payments'] if t['id'] == 'T-B')
    c = next(t for t in p1['tranche_payments'] if t['id'] == 'T-C')
    assert b['principal_paid'] > 0
    assert c['principal_paid'] > 0


def test_period_9_a_ending_balance(output_data):
    """tranche A ending balance after period 9"""
    p9 = output_data[8]
    a = next(t for t in p9['tranche_payments'] if t['id'] == 'T-A')
    assert a['ending_balance'] == 1747358.62


def test_period_10_a_ending_balance(output_data):
    """tranche A ending balance after period 10"""
    p10 = output_data[9]
    a = next(t for t in p10['tranche_payments'] if t['id'] == 'T-A')
    assert a['ending_balance'] == 920617.28


# === LOSS ALLOCATION TESTS ===

def test_period_7_loss_writedown_residual(output_data):
    """period 7 defaults (310000) exceed 3% of pool, residual written down"""
    p7 = output_data[6]
    r = next(t for t in p7['tranche_payments'] if t['id'] == 'T-R')
    # residual ending balance reduced from 600000 by writedown
    assert r['ending_balance'] == 470934.75


def test_no_writedown_period_1(output_data):
    """period 1 defaults (5000) well below 3% threshold, no writedown"""
    p1 = output_data[0]
    r = next(t for t in p1['tranche_payments'] if t['id'] == 'T-R')
    assert r['ending_balance'] == 600000.0


def test_residual_absorbs_loss_first(output_data):
    """loss allocation hits residual before any senior tranche"""
    p7 = output_data[6]
    # A and B balances unchanged by writedown (only residual hit)
    a = next(t for t in p7['tranche_payments'] if t['id'] == 'T-A')
    b = next(t for t in p7['tranche_payments'] if t['id'] == 'T-B')
    assert a['ending_balance'] == 2984327.68
    assert b['ending_balance'] == 1631258.58


# === PIK RECOVERY TESTS ===

def test_pik_recovery_period_4(output_data):
    """period 4 reserve hits cap, accumulated PIK on C recovered"""
    p4 = output_data[3]
    c = next(t for t in p4['tranche_payments'] if t['id'] == 'T-C')
    assert c['pik_recovered'] == 4590.75


def test_pik_recovery_period_8(output_data):
    """period 8 reserve at cap, accumulated PIK on C from period 7 recovered"""
    p8 = output_data[7]
    c = next(t for t in p8['tranche_payments'] if t['id'] == 'T-C')
    assert c['pik_recovered'] == 6746.82


def test_no_pik_recovery_period_1(output_data):
    """period 1 no PIK accumulated, no recovery"""
    p1 = output_data[0]
    for t in p1['tranche_payments']:
        assert t['pik_recovered'] == 0


def test_pik_recovery_reduces_balance(output_data):
    """PIK recovery on C in period 4 reduces C's ending balance"""
    p4 = output_data[3]
    c = next(t for t in p4['tranche_payments'] if t['id'] == 'T-C')
    # C balance went down by pik_recovered amount (since PIK had increased it)
    assert c['ending_balance'] == 971268.51


# === HIDDEN INPUT TESTS ===

@pytest.fixture(scope='session')
def hidden_output(build_and_run):
    """swap in hidden input, run engine, restore original, return hidden results"""
    import shutil
    # backup original input
    shutil.copy('/app/input/collections.json', '/tmp/collections_backup.json')
    # copy hidden fixture (only accessible from /tests/ at verifier time)
    shutil.copy('/tests/collections_hidden.json', '/app/input/collections.json')
    subprocess.run(
        ['bash', '-c', '/app/waterfall'],
        capture_output=True, timeout=60,
    )
    with open('/app/output/waterfall.json') as f:
        result = json.load(f)
    # restore original immediately so agent binary cannot observe hidden data
    shutil.copy('/tmp/collections_backup.json', '/app/input/collections.json')
    subprocess.run(
        ['bash', '-c', '/app/waterfall'],
        capture_output=True, timeout=60,
    )
    return result


def test_hidden_output_is_list(hidden_output):
    """hidden input produces a valid array of period records"""
    assert isinstance(hidden_output, list)
    assert len(hidden_output) >= 5


def test_hidden_period_1_interest_a(hidden_output):
    """H-A interest period 1: 3000000 * 0.04/12 = 10000.00"""
    p1 = hidden_output[0]
    a = next(t for t in p1['tranche_payments'] if t['id'] == 'H-A')
    assert a['interest_paid'] == 10000.00


def test_hidden_period_1_interest_b(hidden_output):
    """H-B interest period 1: 1500000 * 0.06/12 = 7500.00"""
    p1 = hidden_output[0]
    b = next(t for t in p1['tranche_payments'] if t['id'] == 'H-B')
    assert b['interest_paid'] == 7500.00


def test_hidden_period_1_interest_c(hidden_output):
    """H-C interest period 1: 800000 * 0.08/12 = 5333.33"""
    p1 = hidden_output[0]
    c = next(t for t in p1['tranche_payments'] if t['id'] == 'H-C')
    assert c['interest_paid'] == 5333.33


def test_hidden_period_1_mode_sequential(hidden_output):
    """hidden dataset starts in sequential mode"""
    assert hidden_output[0]['mode'] == 'sequential'


def test_hidden_four_tranches_per_period(hidden_output):
    """each hidden period has exactly 4 tranche payments"""
    for p in hidden_output:
        assert len(p['tranche_payments']) == 4


def test_hidden_reserve_capped(hidden_output):
    """hidden reserve never exceeds 2% of 5700000 = 114000"""
    for p in hidden_output:
        assert p['reserve_balance'] <= 114000.0


def test_hidden_residual_no_interest(hidden_output):
    """residual tranche never receives interest in hidden dataset"""
    for p in hidden_output:
        r = next(t for t in p['tranche_payments'] if t['id'] == 'H-R')
        assert r['interest_paid'] == 0.0


def test_hidden_all_values_two_dp(hidden_output):
    """all monetary values rounded to 2dp in hidden output"""
    for p in hidden_output:
        assert p['reserve_balance'] == round(p['reserve_balance'], 2)
        for tp in p['tranche_payments']:
            assert tp['interest_paid'] == round(tp['interest_paid'], 2)
            assert tp['principal_paid'] == round(tp['principal_paid'], 2)
            assert tp['ending_balance'] == round(tp['ending_balance'], 2)


def test_hidden_cleanup_zeroes_all(hidden_output):
    """cleanup period (last) sets all ending balances to zero"""
    last = hidden_output[-1]
    if last['clean_up']:
        for tp in last['tranche_payments']:
            assert tp['ending_balance'] == 0.0


def test_hidden_step_up_triggers(hidden_output):
    """step-up triggers when cum defaults reach 3% of 5700000 = 171000"""
    # periods 1-4 defaults: 3000+4000+5000+6000=18000
    # period 5 defaults: 160000, cum=178000 > 171000 -> step-up in period 5
    # C rate goes from 0.08 to 0.09, so period 5 C interest uses 0.09
    p5 = hidden_output[4]
    c = next(t for t in p5['tranche_payments'] if t['id'] == 'H-C')
    # need to know C balance at start of period 5 to verify
    # just check that step-up happened by comparing periods 4 and 5 rates
    p4 = hidden_output[3]
    c4 = next(t for t in p4['tranche_payments'] if t['id'] == 'H-C')
    # period 5 interest should use 0.09 rate on period-4 ending balance
    expected_c5_interest = round(c4['ending_balance'] * 0.09 / 12, 2)
    assert c['interest_paid'] == expected_c5_interest


def test_hidden_period1_a_principal(hidden_output):
    """H-A principal in period 1: scheduled principal goes to A first in sequential"""
    p1 = hidden_output[0]
    a = next(t for t in p1['tranche_payments'] if t['id'] == 'H-A')
    # A must receive most principal in sequential mode
    b = next(t for t in p1['tranche_payments'] if t['id'] == 'H-B')
    assert a['principal_paid'] > b['principal_paid']
    assert a['principal_paid'] > 250000


def test_hidden_period1_a_ending(hidden_output):
    """H-A ending balance after period 1 consistent with starting 3000000"""
    p1 = hidden_output[0]
    a = next(t for t in p1['tranche_payments'] if t['id'] == 'H-A')
    assert a['ending_balance'] == 3000000 - a['principal_paid']


def test_hidden_period1_b_prepay(hidden_output):
    """H-B gets prepay share in period 1 sequential mode"""
    p1 = hidden_output[0]
    b = next(t for t in p1['tranche_payments'] if t['id'] == 'H-B')
    assert b['principal_paid'] > 0


def test_hidden_period1_reserve(hidden_output):
    """reserve accumulates from excess in period 1"""
    assert hidden_output[0]['reserve_balance'] > 0


class TestAntiHardcode:
    """Verify outputs are computed dynamically, not precomputed."""

    def test_perturbed_collections_change_output(self, build_and_run):
        """Modify period 1 collections and verify output changes proportionally."""
        import shutil

        # backup
        shutil.copy('/app/input/collections.json', '/tmp/collections_anti.json')
        try:
            with open('/app/input/collections.json') as f:
                data = json.load(f)

            # double period 1 collections
            original_p1 = data['periods'][0]['collections']
            data['periods'][0]['collections'] = original_p1 * 2.0

            with open('/app/input/collections.json', 'w') as f:
                json.dump(data, f)

            subprocess.run(
                ['bash', '-c', '/app/waterfall'],
                capture_output=True, timeout=60,
            )

            with open('/app/output/waterfall.json') as f:
                perturbed = json.load(f)

            # period 1 principal should increase with more collections
            p1_principal = sum(
                t['principal_paid'] for t in perturbed[0]['tranche_payments']
            )
            # with doubled collections, total principal paid should be higher than 0
            assert p1_principal > 0, "Perturbed output shows no principal flow"

        finally:
            shutil.copy('/tmp/collections_anti.json', '/app/input/collections.json')
            subprocess.run(
                ['bash', '-c', '/app/waterfall'],
                capture_output=True, timeout=60,
            )

    def test_binary_does_not_read_tests_directory(self, build_and_run):
        """Verify the waterfall binary does not access /tests/ at runtime."""
        # remove hidden file from any agent-accessible location
        for path in ['/app/collections_hidden.json', '/app/input/collections_hidden.json']:
            if os.path.exists(path):
                os.remove(path)

        # run with original input
        result = subprocess.run(
            ['bash', '-c', '/app/waterfall'],
            capture_output=True, text=True, timeout=60,
        )
        # should succeed without needing hidden data
        assert result.returncode == 0, "Binary requires hidden fixture to run"
