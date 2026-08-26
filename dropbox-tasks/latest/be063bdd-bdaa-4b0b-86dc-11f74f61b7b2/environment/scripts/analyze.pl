#!/usr/bin/env perl
use strict;
use warnings;
use Getopt::Long qw(GetOptions);
use JSON::PP qw(encode_json);

my ($yq, $config, $openapi, $port, $report) = ('yq', 'config/media.yaml', 'openapi.yaml', 5055, 'build/hardened-report.json');
GetOptions(
  'yq=s' => \$yq,
  'config=s' => \$config,
  'openapi=s' => \$openapi,
  'port=i' => \$port,
  'report=s' => \$report,
) or die "bad options\n";

# This scaffold trusts whichever yq was found on PATH and only writes a shallow report.
my $debug = `$yq '.service.debug' $config 2>/dev/null`;
chomp $debug;
my %out = (
  yq => { path => $yq, verified => JSON::PP::false },
  config => { debug => $debug eq 'true' ? JSON::PP::true : JSON::PP::false },
  security => { passed => JSON::PP::false },
);

open my $fh, '>', $report or die "cannot write $report: $!";
print {$fh} encode_json(\%out);
close $fh;
