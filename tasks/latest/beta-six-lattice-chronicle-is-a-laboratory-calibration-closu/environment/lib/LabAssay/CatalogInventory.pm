package LabAssay::CatalogInventory;
use strict;
use warnings;
use JSON::PP qw(decode_json encode_json);

# Working laboratory baseline: inventory formulation catalog entries.
# Lattice chronicle closure kernels live under LabLattice::Closure (agent-built).

sub summarize {
    my ($catalog_path) = @_;
    open my $fh, '<', $catalog_path or die "catalog: $!";
    my $doc = decode_json(do { local $/; <$fh> });
    close $fh;
    my @ids = sort map { $_->{formulation_id} } @{ $doc->{formulations} // [] };
    return {
        schema => 'lab-assay-catalog-inventory-v1',
        formulation_count => scalar @ids,
        formulation_ids => \@ids,
    };
}

sub write_summary {
    my ($catalog_path, $out_path) = @_;
    my $summary = summarize($catalog_path);
    open my $ofh, '>', $out_path or die "inventory write: $!";
    print {$ofh} encode_json($summary), "\n";
    close $ofh;
    return $summary;
}

1;
