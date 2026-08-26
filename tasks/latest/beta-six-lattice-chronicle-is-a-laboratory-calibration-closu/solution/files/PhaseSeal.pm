package ConchingAssay::WalkMath::PhaseSeal;
use strict;
use warnings;
use Digest::SHA qw(sha256_hex);

sub ledger_triad_digest {
    my ($bind_digest, $spine_digest, $adjacency_digest) = @_;
    return sha256_hex("$bind_digest|$spine_digest|$adjacency_digest");
}

sub topology_bundle_digest {
    my ($concordance_digest, $cycle_digest) = @_;
    return sha256_hex("$concordance_digest|$cycle_digest");
}

sub closure_bundle_digest {
    my ($ledger_triad, $topology_bundle) = @_;
    return sha256_hex("$ledger_triad|$topology_bundle");
}

sub build {
    my (
        $capture_digest, $snapshot_digest, $epoch, $bind_digest,
        $spine_digest, $adjacency_digest, $concordance_digest, $cycle_digest
    ) = @_;
    die "phase_seal requires capture, snapshot, epoch, and five closure digests\n"
      unless defined $capture_digest
      && defined $snapshot_digest
      && defined $epoch
      && defined $bind_digest
      && defined $spine_digest
      && defined $adjacency_digest
      && defined $concordance_digest
      && defined $cycle_digest;
    my $epoch_after = $epoch + 1;
    my $audit_commitment = Digest::SHA::sha256_hex("fuse|$epoch|$epoch_after");
    my $ledger_triad = ledger_triad_digest($bind_digest, $spine_digest, $adjacency_digest);
    my $topology_bundle = topology_bundle_digest($concordance_digest, $cycle_digest);
    my $closure_bundle = closure_bundle_digest($ledger_triad, $topology_bundle);
    my $bind = Digest::SHA::sha256_hex(
        "$capture_digest|$snapshot_digest|$epoch|$bind_digest|$spine_digest|$adjacency_digest|$concordance_digest|$cycle_digest|$audit_commitment|$ledger_triad|$topology_bundle|$closure_bundle"
    );
    return {
        schema => 'phase-stabilization-seal-v2',
        epoch => $epoch,
        capture_digest => $capture_digest,
        snapshot_digest => $snapshot_digest,
        spine_digest => $spine_digest,
        adjacency_digest => $adjacency_digest,
        concordance_digest => $concordance_digest,
        cycle_digest => $cycle_digest,
        audit_commitment => $audit_commitment,
        ledger_triad_digest => $ledger_triad,
        topology_bundle_digest => $topology_bundle,
        closure_bundle_digest => $closure_bundle,
        phase_seal => $bind,
    };
}

1;
