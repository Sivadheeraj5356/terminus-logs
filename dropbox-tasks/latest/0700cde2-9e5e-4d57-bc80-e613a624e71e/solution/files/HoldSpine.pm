package ConchingAssay::WalkMath::HoldSpine;
use strict;
use warnings;
use Digest::SHA qw(sha256_hex);
use JSON::PP qw(encode_json decode_json);

sub build {
    my ($capture) = @_;
    my @rows;
    my $seq = 1;
    for my $batch (@{ $capture->{batches} }) {
        for my $hp (@{ $batch->{hold_profiles} // [] }) {
            push @rows, {
                spine_seq => $seq,
                batch_id => $batch->{batch_id},
                polymorph => $hp->{polymorph},
                effective_hold_s => 0 + int($hp->{effective_hold_s}),
                temp_c => $hp->{temp_c},
            };
            $seq++;
        }
    }
    my $digest = digest_from_rows(\@rows);
    return {
        schema => 'hold-spine-ledger-v1',
        rows => \@rows,
        spine_digest => $digest,
    };
}

sub digest_from_rows {
    my ($rows) = @_;
    my @lines;
    for my $r (@$rows) {
        push @lines, join('|',
            $r->{spine_seq},
            $r->{batch_id},
            $r->{polymorph},
            0 + int($r->{effective_hold_s}),
            $r->{temp_c},
        );
    }
    return sha256_hex(join("\n", @lines));
}

sub write {
    my ($path, $capture) = @_;
    my $payload = build($capture);
    open my $fh, '>', $path or die "hold-spine write: $!";
    print {$fh} encode_json($payload), "\n";
    close $fh;
    return $payload;
}

sub read {
    my ($path) = @_;
    open my $fh, '<', $path or die "hold-spine read: $!";
    my $raw = do { local $/; <$fh> };
    close $fh;
    return decode_json($raw);
}

sub verify_against_capture {
    my ($ledger, $capture) = @_;
    my $want = build($capture);
    die "hold-spine spine_digest mismatch\n"
      unless ($ledger->{spine_digest} // '') eq $want->{spine_digest};
    my $recomputed = digest_from_rows($ledger->{rows} // []);
    die "hold-spine rows digest mismatch\n"
      unless $recomputed eq ($ledger->{spine_digest} // '');
    return $ledger->{spine_digest};
}

1;
