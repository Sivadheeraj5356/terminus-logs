#!/bin/bash
CP="${REACTOR_CLASSES:-/app/classes}"
exec java -cp "$CP" brace.EchoB "$@"
