#!/bin/bash
CP="${REACTOR_CLASSES:-/app/classes}"
exec java -cp "$CP" span.EchoC "$@"
