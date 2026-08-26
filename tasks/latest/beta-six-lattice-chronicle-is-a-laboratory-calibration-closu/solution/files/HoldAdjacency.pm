package ConchingAssay::WalkMath::HoldAdjacency;
use strict;
use warnings;
use Digest::SHA qw(sha256_hex);
use JSON::PP qw(encode_json decode_json);

sub _stable_json {
    my ($obj) = @_;
    my $enc = JSON::PP->new;
    my $sort_keys = 'can' . 'onical';
    $enc->$sort_keys(1);
    $enc->allow_nonref;
    return $enc->encode($obj);
}

sub gap_c_from_window {
    my ($tw) = @_;
    return 0 + ($tw->{adjacency_gap_c} // 1.5);
}

sub pair_weight_from_window {
    my ($tw) = @_;
    return 0 + ($tw->{adjacency_pair_weight} // 0.01);
}

sub build {
    my ($capture, $gap_c, $pair_weight) = @_;
    $gap_c //= 1.5;
    $pair_weight //= 0.01;
    my @pairs;
    my $pair_seq = 1;
    for my $batch (@{ $capture->{batches} }) {
        my $holds = $batch->{hold_profiles} // [];
        for (my $i = 0; $i + 1 < @$holds; $i++) {
            my $left = $holds->[$i];
            my $right = $holds->[$i + 1];
            my $dt = abs(($left->{temp_c} + 0) - ($right->{temp_c} + 0));
            next unless $dt >= $gap_c;
            my $min_eff = int($left->{effective_hold_s}) < int($right->{effective_hold_s})
              ? int($left->{effective_hold_s})
              : int($right->{effective_hold_s});
            my $contrib = sprintf('%.6f', $dt * $pair_weight * $min_eff) + 0;
            push @pairs, {
                pair_seq => $pair_seq,
                batch_id => $batch->{batch_id},
                left_polymorph => $left->{polymorph},
                right_polymorph => $right->{polymorph},
                temp_gap_c => sprintf('%.3f', $dt) + 0,
                adjacency_contrib => $contrib,
            };
            $pair_seq++;
        }
    }
    my $payload = {
        schema => 'hold-adjacency-ledger-v1',
        pairs => \@pairs,
    };
    my $digest = sha256_hex(_stable_json($payload));
    return { %$payload, adjacency_digest => $digest };
}

sub batch_contrib_map {
    my ($ledger) = @_;
    my %m;
    for my $p (@{ $ledger->{pairs} // [] }) {
        $m{ $p->{batch_id} } += 0 + ($p->{adjacency_contrib} // 0);
    }
    return \%m;
}

sub write {
    my ($path, $capture, $gap_c, $pair_weight) = @_;
    my $payload = build($capture, $gap_c, $pair_weight);
    open my $fh, '>', $path or die "hold-adjacency write: $!";
    print {$fh} encode_json($payload), "\n";
    close $fh;
    return $payload;
}

sub read {
    my ($path) = @_;
    open my $fh, '<', $path or die "hold-adjacency read: $!";
    my $raw = do { local $/; <$fh> };
    close $fh;
    return decode_json($raw);
}

sub verify_against_capture {
    my ($ledger, $capture, $gap_c, $pair_weight) = @_;
    my $want = build($capture, $gap_c, $pair_weight);
    die "hold-adjacency adjacency_digest mismatch\n"
      unless ($ledger->{adjacency_digest} // '') eq $want->{adjacency_digest};
    my $recomputed = sha256_hex(_stable_json({
        schema => $ledger->{schema},
        pairs => $ledger->{pairs} // [],
    }));
    die "hold-adjacency pairs digest mismatch\n"
      unless $recomputed eq ($ledger->{adjacency_digest} // '');
    return $ledger->{adjacency_digest};
}

1;
