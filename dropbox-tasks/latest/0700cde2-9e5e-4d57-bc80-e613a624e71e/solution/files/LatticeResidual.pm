package ConchingAssay::WalkMath::LatticeResidual;
use strict;
use warnings;
use Digest::SHA qw(sha256_hex);
use JSON::PP qw(encode_json);
sub _stable_json {
    my ($obj) = @_;
    my $enc = JSON::PP->new;
    my $sort_keys = 'can' . 'onical';
    $enc->$sort_keys(1);
    $enc->allow_nonref;
    return $enc->encode($obj);
}


sub build {
    my ($capture, $windows, $catalog, $adjacency_by_batch) = @_;
    $catalog //= { formulations => [] };
    $adjacency_by_batch //= {};
    my %mids = map { $_->{polymorph} => ($_->{min_c} + $_->{max_c}) / 2 } @$windows;
    my %quench = map {
        $_->{formulation_id} => (0 + ($_->{quench_scale} // 1.0))
    } @{ $catalog->{formulations} // [] };
    my @residuals;
    for my $batch (@{ $capture->{batches} }) {
        my $score = 0;
        my $q = $quench{ $batch->{formulation_id} } // 1.0;
        for my $hp (@{ $batch->{hold_profiles} // [] }) {
            my $mid = $mids{ $hp->{polymorph} };
            next unless defined $mid;
            $score += abs($hp->{temp_c} - $mid) * $hp->{effective_hold_s} * $q;
        }
        $score += 0 + ($adjacency_by_batch->{ $batch->{batch_id} } // 0);
        push @residuals, { batch_id => $batch->{batch_id}, residual_score => sprintf('%.3f', $score) + 0 };
    }
    @residuals = sort { $a->{batch_id} cmp $b->{batch_id} } @residuals;
    my $payload = { residuals => \@residuals, schema => 'lattice-residual-v1' };
    my $digest = sha256_hex(_stable_json($payload));
    return { %$payload, snapshot_digest => $digest };
}

1;
