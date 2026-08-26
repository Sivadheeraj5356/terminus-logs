package ConchingAssay::WalkMath::BindManifest;
use strict;
use warnings;
use Digest::SHA qw(sha256_hex);
use JSON::PP qw(encode_json);

sub write {
    my ($path, $traces_dir, $window_path, $shear_bonus) = @_;
    my $payload = {
        schema => 'chronicle-bind-manifest-v1',
        kiln_traces_path => $traces_dir,
        conching_window_path => $window_path,
        shear_bonus_hz => 0 + $shear_bonus,
        bind_digest => sha256_hex("$traces_dir|$window_path"),
    };
    open my $fh, '>', $path or die "manifest: $!";
    print {$fh} encode_json($payload), "\n";
    close $fh;
    return $payload;
}

sub read {
    my ($path) = @_;
    open my $fh, '<', $path or die "manifest read: $!";
    my $raw = do { local $/; <$fh> };
    close $fh;
    return JSON::PP->new->decode($raw);
}

1;
