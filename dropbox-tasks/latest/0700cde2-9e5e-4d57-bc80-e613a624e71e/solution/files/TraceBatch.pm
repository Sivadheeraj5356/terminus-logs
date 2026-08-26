package ConchingAssay::WalkMath::TraceBatch;
use strict;
use warnings;
use JSON::PP qw(decode_json);

sub load_batches {
    my ($batch_dir) = @_;
    my @rows;
    for my $path (sort glob("$batch_dir/*.jsonl")) {
        open my $fh, '<', $path or die "open $path: $!";
        while (my $line = <$fh>) {
            chomp $line;
            next unless length $line;
            my $obj = decode_json($line);
            next if ($obj->{event} // '') eq 'MARKER';
            push @rows, $obj;
        }
        close $fh;
    }
    @rows = sort {
        ($a->{batch_id} cmp $b->{batch_id})
            || ($a->{cycle_seq} <=> $b->{cycle_seq})
            || ($a->{ts} cmp $b->{ts})
    } @rows;
    return \@rows;
}

1;
