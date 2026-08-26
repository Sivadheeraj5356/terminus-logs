package ConchingAssay::WalkMath::Epoch;
use strict;
use warnings;

sub read_epoch {
    my ($path) = @_;
    open my $fh, '<', $path or return 1;
    my $v = <$fh>;
    close $fh;
    chomp $v;
    return $v =~ /^\d+$/ ? int($v) : 1;
}

sub bump {
    my ($path) = @_;
    my $cur = read_epoch($path);
    my $next = $cur + 1;
    open my $fh, '>', $path or die "epoch write: $!";
    print {$fh} "$next\n";
    close $fh;
    return $next;
}

1;
