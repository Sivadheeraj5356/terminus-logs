package ConchingAssay::WalkMath::CrossBatchConcordance;
use strict;
use warnings;
use Digest::SHA qw(sha256_hex);
use JSON::PP qw(encode_json decode_json);

sub _stable_json {
    my ($obj) = @_;
    my $enc = JSON::PP->new->canonical(1);
    $enc->allow_nonref;
    return $enc->encode($obj);
}

sub _perl_number {
    my ($value) = @_;
    return int($value) if int($value) == $value;
    return 0 + $value;
}

sub build {
    my ($capture, $residual) = @_;
    my %scores = map {
        $_->{batch_id} => 0 + ($_->{residual_score} // 0)
    } @{ $residual->{residuals} // [] };
    my @batches = sort {
        $a->{batch_id} cmp $b->{batch_id}
    } @{ $capture->{batches} // [] };
    my @rows;

    for (my $i = 0; $i < @batches; $i++) {
        for (my $j = $i + 1; $j < @batches; $j++) {
            my ($left, $right) = ($batches[$i], $batches[$j]);
            my (%left_holds, %right_holds);
            $left_holds{ $_->{polymorph} } += int($_->{effective_hold_s})
              for @{ $left->{hold_profiles} // [] };
            $right_holds{ $_->{polymorph} } += int($_->{effective_hold_s})
              for @{ $right->{hold_profiles} // [] };
            my @shared = sort grep { exists $right_holds{$_} } keys %left_holds;
            my $shared_hold = 0;
            for my $poly (@shared) {
                $shared_hold += $left_holds{$poly} < $right_holds{$poly}
                  ? $left_holds{$poly}
                  : $right_holds{$poly};
            }
            my $gap = sprintf('%.3f', abs(
                ($scores{$left->{batch_id}} // 0) -
                ($scores{$right->{batch_id}} // 0)
            )) + 0;
            my $denominator = $shared_hold + $gap;
            my $score = $denominator
              ? sprintf('%.6f', $shared_hold / $denominator) + 0
              : 1;
            push @rows, {
                left_batch_id => $left->{batch_id},
                right_batch_id => $right->{batch_id},
                shared_polymorphs => \@shared,
                shared_effective_hold_s => $shared_hold,
                residual_gap => _perl_number($gap),
                concordance_score => _perl_number($score),
            };
        }
    }

    my $payload = {
        schema => 'cross-batch-concordance-v1',
        rows => \@rows,
    };
    return {
        %$payload,
        concordance_digest => sha256_hex(_stable_json($payload)),
    };
}

sub write {
    my ($path, $capture, $residual) = @_;
    my $payload = build($capture, $residual);
    open my $fh, '>', $path or die "cross-batch concordance write: $!";
    print {$fh} encode_json($payload), "\n";
    close $fh;
    return $payload;
}

sub read {
    my ($path) = @_;
    open my $fh, '<', $path or die "cross-batch concordance read: $!";
    my $raw = do { local $/; <$fh> };
    close $fh;
    return decode_json($raw);
}

sub verify {
    my ($ledger, $capture, $residual) = @_;
    my $want = build($capture, $residual);
    my $self_digest = sha256_hex(_stable_json({
        schema => $ledger->{schema},
        rows => $ledger->{rows} // [],
    }));
    die "cross-batch concordance digest mismatch\n"
      unless ($ledger->{concordance_digest} // '') eq $self_digest;
    my @got_capture = map {
        {
            left_batch_id => $_->{left_batch_id},
            right_batch_id => $_->{right_batch_id},
            shared_polymorphs => $_->{shared_polymorphs},
            shared_effective_hold_s => $_->{shared_effective_hold_s},
        }
    } @{ $ledger->{rows} // [] };
    my @want_capture = map {
        {
            left_batch_id => $_->{left_batch_id},
            right_batch_id => $_->{right_batch_id},
            shared_polymorphs => $_->{shared_polymorphs},
            shared_effective_hold_s => $_->{shared_effective_hold_s},
        }
    } @{ $want->{rows} // [] };
    die "cross-batch concordance capture projection mismatch\n"
      unless _stable_json(\@got_capture) eq _stable_json(\@want_capture);
    return $ledger->{concordance_digest};
}

1;
