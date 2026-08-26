package ConchingAssay::WalkMath::AuditLog;
use strict;
use warnings;
use JSON::PP qw(encode_json);
use Fcntl qw(SEEK_END);

sub append {
    my ($path, $entry) = @_;
    open my $fh, '>>', $path or die "audit: $!";
    print {$fh} encode_json($entry), "\n";
    close $fh;
    return 1;
}

1;
