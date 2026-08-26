package ConchingAssay::WalkMath::PeakCapture;
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


sub _match_poly {
    my ($temp, $windows) = @_;
    for my $w (@$windows) {
        return $w->{polymorph} if $temp >= $w->{min_c} && $temp <= $w->{max_c};
    }
    return undef;
}

sub _eff_hold {
    my ($dur, $shear, $bonus) = @_;
    my $extra = ($shear >= $bonus) ? int($dur * 0.1) : 0;
    return $dur + $extra;
}

sub build {
    my ($events, $windows, $shear_bonus) = @_;
    my %batches;
    push @{ $batches{ $_->{batch_id} } }, $_ for @$events;
    my @batch_rows;
    for my $bid (sort keys %batches) {
        my @evs = @{ $batches{$bid} };
        my @holds;
        for my $ev (@evs) {
            next unless ($ev->{event} // '') eq 'HOLD';
            my $poly = _match_poly($ev->{temp_c}, $windows);
            next unless defined $poly;
            push @holds, {
                polymorph => $poly,
                effective_hold_s => _eff_hold($ev->{duration_s} // 0, $ev->{shear_hz} // 0, $shear_bonus),
                temp_c => ($ev->{temp_c} + 0) * 1.0,
            };
        }
        push @batch_rows, {
            batch_id => $bid,
            formulation_id => $evs[0]{formulation_id},
            event_count => scalar @evs,
            hold_profiles => \@holds,
        };
    }
    my $payload = { batches => \@batch_rows, schema => 'thermal-cycle-capture-v1' };
    my $digest = sha256_hex(_stable_json($payload));
    return { %$payload, capture_digest => $digest };
}

1;
