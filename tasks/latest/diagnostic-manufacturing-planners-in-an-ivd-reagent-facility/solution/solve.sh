#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILES="${SCRIPT_DIR}/files"

cp "${FILES}/order/SpecOrder.java" /app/src/main/java/com/blendcert/order/SpecOrder.java
cp "${FILES}/solve/BandFeasibility.java" /app/src/main/java/com/blendcert/solve/BandFeasibility.java
cp "${FILES}/certify/DualPrice.java" /app/src/main/java/com/blendcert/certify/DualPrice.java
cp "${FILES}/certify/GapBound.java" /app/src/main/java/com/blendcert/certify/GapBound.java
cp "${FILES}/bind/BlendModelBind.java" /app/src/main/java/com/blendcert/bind/BlendModelBind.java
cp "${FILES}/seal/FeasibilityDigest.java" /app/src/main/java/com/blendcert/seal/FeasibilityDigest.java
cp "${FILES}/stage/SolveStage.java" /app/src/main/java/com/blendcert/stage/SolveStage.java
cp "${FILES}/stage/CertifyStage.java" /app/src/main/java/com/blendcert/stage/CertifyStage.java

cd /app
mvn -o -q -f /app/pom.xml package -DskipTests -Dmaven.repo.local=/opt/maven-cache/repository

java -jar /app/target/blendcert.jar bind
java -jar /app/target/blendcert.jar solve
java -jar /app/target/blendcert.jar certify
java -jar /app/target/blendcert.jar seal
