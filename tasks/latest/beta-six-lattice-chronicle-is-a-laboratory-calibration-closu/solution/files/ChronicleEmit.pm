package ConchingAssay::WalkMath::ChronicleEmit;
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


sub _dominant {
    my ($holds, $windows) = @_;
    my %need = map { $_->{polymorph} => $_->{hold_min_s} } @$windows;
    my %acc;
    $acc{ $_->{polymorph} } += $_->{effective_hold_s} for @$holds;
    my @ranked = sort { $acc{$b} <=> $acc{$a} || $a cmp $b } keys %acc;
    for my $poly (@ranked) {
        return $poly if $acc{$poly} >= ($need{$poly} // 0);
    }
    return $ranked[0] // 'NONE';
}

sub build {
    my ($capture, $residual, $seal, $catalog, $windows) = @_;
    my %forms = map { $_->{formulation_id} => $_ } @{ $catalog->{formulations} };
    my %res = map { $_->{batch_id} => $_->{residual_score} } @{ $residual->{residuals} };
    my @tracks;
    for my $batch (@{ $capture->{batches} }) {
        my $fid = $batch->{formulation_id};
        my $form = $forms{$fid};
        my $dom = _dominant($batch->{hold_profiles} // [], $windows);
        my $quench = 0 + ($form->{quench_scale} // 1.0);
        push @tracks, {
            batch_id => $batch->{batch_id},
            formulation_id => $fid,
            seed_polymorph => $form->{seed_polymorph},
            dominant_polymorph => $dom,
            residual_score => $res{ $batch->{batch_id} } // 0,
            quench_scale => $quench,
            transition => ($dom ne $form->{seed_polymorph}) ? JSON::PP::true : JSON::PP::false,
        };
    }
    @tracks = sort { $a->{batch_id} cmp $b->{batch_id} } @tracks;
    my $body = {
        schema => 'beta-six-lattice-chronicle-v1',
        epoch => $seal->{epoch},
        phase_seal => $seal->{phase_seal},
        lattice_walks => \@tracks,
    };
    my $digest = sha256_hex(_stable_json($body));
    my $walk_digest = sha256_hex(_stable_json(\@tracks));
    return { %$body, chronicle_digest => $digest, walk_content_digest => $walk_digest };
}

1;
