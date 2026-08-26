#!/bin/sh
set -eu

response=$(/app/arena --wire ping)
test "$response" = "TIDEVAULT_WIRE_V1
READY	1
END"
