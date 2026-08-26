package KilnTemper::Chronicle::RecipeFlavor;
use strict;
use warnings;

# Decoy flavor scoring — not on atlas chronicle hot path
sub score_batch {
    my ($formulation, $events) = @_;
    my $base = ($formulation->{cocoa_solids_pct} // 0) * 0.01;
    my $n = scalar @$events;
    return sprintf('%.2f', $base + $n * 0.003);
}

1;
