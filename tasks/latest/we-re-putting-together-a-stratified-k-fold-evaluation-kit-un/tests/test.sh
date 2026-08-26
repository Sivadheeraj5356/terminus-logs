#!/bin/bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
chmod 700 /logs/verifier

if [ "$PWD" = "/" ]; then
  echo 0 > /logs/verifier/reward.txt
  echo "Error: No working directory set." >&2
  exit 1
fi

# Verifier-owned offline rebuild: never invoke the agent-editable /app/pom.xml.
# Build root lives under root-only /logs/verifier and only receives Java sources
# copied from /app/src/main/java (symlinks stripped), so package cannot embed
# /tests or other absolute verifier paths into the jar.
BUILD_ROOT=/logs/verifier/maven-build
rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT/src/main/java"
cp /tests/verifier-pom.xml "$BUILD_ROOT/pom.xml"
if [ ! -d /app/src/main/java ]; then
  echo 0 > /logs/verifier/reward.txt
  echo "Error: missing /app/src/main/java for verifier build." >&2
  exit 1
fi
cp -a /app/src/main/java/. "$BUILD_ROOT/src/main/java/"
# Drop symlinks that could escape the sandbox into /tests or elsewhere.
find "$BUILD_ROOT/src" -type l -delete

mkdir -p /app/target
if ! mvn -q -o -f "$BUILD_ROOT/pom.xml" -DskipTests package; then
  echo 0 > /logs/verifier/reward.txt
  echo "Error: verifier Maven package failed." >&2
  exit 1
fi

JAR_SRC="$BUILD_ROOT/target/fold-assembler-1.0.0.jar"
if [ ! -f "$JAR_SRC" ]; then
  echo 0 > /logs/verifier/reward.txt
  echo "Error: verifier Maven package did not produce fold-assembler jar." >&2
  exit 1
fi
cp -f "$JAR_SRC" /app/target/fold-assembler-1.0.0.jar
chmod a+r /app/target/fold-assembler-1.0.0.jar

# Do not export PYTHONPATH=/tests — foldctl subprocesses must not inherit a path
# that can import verifier reference modules. Pytest loads /tests/test_outputs.py
# directly and resolves local imports from that directory.
python3 -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
