package ConchingAssay::WalkMath::ConcordanceCycle;
use strict;
use warnings;
use Digest::SHA qw(sha256_hex);
use JSON::PP qw(encode_json decode_json);

sub _stable_json {
    my ($obj) = @_;
    return JSON::PP->new->canonical(1)->allow_nonref->encode($obj);
}

sub _number {
    my ($value) = @_;
    return int($value) if int($value) == $value;
    return 0 + $value;
}

sub _hold_totals {
    my ($batch) = @_;
    my %totals;
    $totals{ $_->{polymorph} } += int($_->{effective_hold_s})
      for @{ $batch->{hold_profiles} // [] };
    return \%totals;
}

sub build {
    my ($capture, $concordance) = @_;
    my @batches = sort { $a->{batch_id} cmp $b->{batch_id} }
      @{ $capture->{batches} // [] };
    my %edges = map {
        ($_->{left_batch_id} . '|' . $_->{right_batch_id}) => $_
    } @{ $concordance->{rows} // [] };
    my @rows;

    for (my $i = 0; $i < @batches; $i++) {
        for (my $j = $i + 1; $j < @batches; $j++) {
            for (my $k = $j + 1; $k < @batches; $k++) {
                my @triple = @batches[$i, $j, $k];
                my @ids = map { $_->{batch_id} } @triple;
                my @totals = map { _hold_totals($_) } @triple;
                my @common = sort grep {
                    exists $totals[1]->{$_} && exists $totals[2]->{$_}
                } keys %{ $totals[0] };
                my $common_hold = 0;
                for my $poly (@common) {
                    my $least = $totals[0]->{$poly};
                    $least = $totals[1]->{$poly} if $totals[1]->{$poly} < $least;
                    $least = $totals[2]->{$poly} if $totals[2]->{$poly} < $least;
                    $common_hold += $least;
                }
                my @pairs = (
                    "$ids[0]|$ids[1]",
                    "$ids[0]|$ids[2]",
                    "$ids[1]|$ids[2]",
                );
                my @edge_rows;
                my @scores;
                for my $pair (@pairs) {
                    my $edge = $edges{$pair}
                      or die "cycle basis missing concordance edge $pair\n";
                    my $score = _number($edge->{concordance_score} // 0);
                    push @scores, $score;
                    push @edge_rows, { pair => $pair, score => $score };
                }
                my $mean = @scores
                  ? sprintf('%.6f', ($scores[0] + $scores[1] + $scores[2]) / 3) + 0
                  : 1;
                push @rows, {
                    batch_ids => \@ids,
                    common_polymorphs => \@common,
                    common_effective_hold_s => $common_hold,
                    edge_pairs => \@pairs,
                    edge_scores => \@scores,
                    edge_commitment => sha256_hex(_stable_json(\@edge_rows)),
                    cycle_mean => _number($mean),
                };
            }
        }
    }
    my $payload = {
        schema => 'concordance-cycle-basis-v1',
        rows => \@rows,
    };
    return {
        %$payload,
        cycle_digest => sha256_hex(_stable_json($payload)),
    };
}

sub write {
    my ($path, $capture, $concordance) = @_;
    my $payload = build($capture, $concordance);
    open my $fh, '>', $path or die "concordance cycle write: $!";
    print {$fh} encode_json($payload), "\n";
    close $fh;
    return $payload;
}

sub read {
    my ($path) = @_;
    open my $fh, '<', $path or die "concordance cycle read: $!";
    my $raw = do { local $/; <$fh> };
    close $fh;
    return decode_json($raw);
}

sub verify {
    my ($basis, $capture, $concordance) = @_;
    my $self_digest = sha256_hex(_stable_json({
        schema => $basis->{schema},
        rows => $basis->{rows} // [],
    }));
    die "concordance cycle digest mismatch\n"
      unless ($basis->{cycle_digest} // '') eq $self_digest;
    my $want = build($capture, $concordance);
    die "concordance cycle closure mismatch\n"
      unless _stable_json($basis->{rows} // []) eq _stable_json($want->{rows});
    return $basis->{cycle_digest};
}

1;
