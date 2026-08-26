package ConchingAssay::WalkMath::EmitLane;
use strict;
use warnings;
use JSON::PP qw(decode_json encode_json);
use ConchingAssay::WalkMath::PhaseSeal;
use ConchingAssay::WalkMath::ChronicleEmit;
use ConchingAssay::WalkMath::Epoch;
use ConchingAssay::WalkMath::AuditLog;
use ConchingAssay::WalkMath::BindManifest;
use ConchingAssay::WalkMath::HoldSpine;
use ConchingAssay::WalkMath::HoldAdjacency;
use ConchingAssay::WalkMath::CrossBatchConcordance;
use ConchingAssay::WalkMath::ConcordanceCycle;

sub run {
    my (%opt) = @_;
    my $manifest = ConchingAssay::WalkMath::BindManifest::read('/app/state/chronicle-bind-manifest.json');
    my $catalog = _load_json($opt{'--lattice-invariant-catalog'});
    my $window_path = $manifest->{conching_window_path}
        or die "manifest missing conching_window_path\n";
    my $tw = _load_json($window_path);
    my $epoch_path = '/app/var/walk_epoch';
    my $epoch = ConchingAssay::WalkMath::Epoch::read_epoch($epoch_path);

    my $capture = _load_json('/app/state/dsc-peak-capture.json');
    my $residual = _load_json('/app/state/torque-residual-snapshot.json');
    my $spine = ConchingAssay::WalkMath::HoldSpine::read('/app/state/hold-spine-ledger.json');
    my $spine_digest = ConchingAssay::WalkMath::HoldSpine::verify_against_capture($spine, $capture);
    my $gap_c = ConchingAssay::WalkMath::HoldAdjacency::gap_c_from_window($tw);
    my $pair_w = ConchingAssay::WalkMath::HoldAdjacency::pair_weight_from_window($tw);
    my $adjacency = ConchingAssay::WalkMath::HoldAdjacency::read('/app/state/hold-adjacency-ledger.json');
    my $adjacency_digest = ConchingAssay::WalkMath::HoldAdjacency::verify_against_capture(
        $adjacency, $capture, $gap_c, $pair_w
    );
    my $concordance = ConchingAssay::WalkMath::CrossBatchConcordance::read(
        '/app/state/cross-batch-concordance.json'
    );
    my $concordance_digest = ConchingAssay::WalkMath::CrossBatchConcordance::verify(
        $concordance, $capture, $residual
    );
    my $cycles = ConchingAssay::WalkMath::ConcordanceCycle::read(
        '/app/state/concordance-cycle-basis.json'
    );
    my $cycle_digest = ConchingAssay::WalkMath::ConcordanceCycle::verify(
        $cycles, $capture, $concordance
    );

    my $seal = ConchingAssay::WalkMath::PhaseSeal::build(
        $capture->{capture_digest}, $residual->{snapshot_digest}, $epoch,
        $manifest->{bind_digest} // '',
        $spine_digest,
        $adjacency_digest,
        $concordance_digest,
        $cycle_digest,
    );
    {
        open my $pfh, '>', '/app/state/polymorph-walk-seal.json' or die $!;
        print {$pfh} encode_json($seal), "\n";
        close $pfh;
    }

    my $atlas = ConchingAssay::WalkMath::ChronicleEmit::build(
        $capture, $residual, $seal, $catalog, $tw->{windows}
    );
    {
        open my $ofh, '>', $opt{'--output'} or die $!;
        print {$ofh} encode_json($atlas), "\n";
        close $ofh;
    }

    my $new_epoch = ConchingAssay::WalkMath::Epoch::bump($epoch_path);
    ConchingAssay::WalkMath::AuditLog::append('/app/var/chronicle-audit.log.jsonl', {
        action => 'fuse',
        epoch_before => $epoch,
        epoch_after => $new_epoch,
        chronicle_digest => $atlas->{chronicle_digest},
    });

    return $atlas;
}

sub _load_json {
    my ($path) = @_;
    open my $fh, '<', $path or die $!;
    my $obj = decode_json(do { local $/; <$fh> });
    close $fh;
    return $obj;
}

1;
