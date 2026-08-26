#!/bin/bash
set -euo pipefail

# Oracle for the Meridian Ridge spectral service freeze audit.
# Sequence: reconcile the in-force decision record (registry + archive),
# repair the pom against it, bring the query layer and estimator into
# compliance, rebuild offline, verify the endpoints, and file the dossier.
#
# Every provenance value written to the dossier is DERIVED here from the
# station archive and the review registry — nothing is transcribed from a
# saved answer. The derivations are deterministic: the same archive and
# registry produce the same dossier on every run.

PSQL="psql -h 127.0.0.1 -U meridian -d meridian -qtA"
SVC=/app/service
JAVA_DIR=$SVC/src/main/java/org/mrgo/spectra
ARCH=/app/archive

# ---------------------------------------------------------------- database up
for _ in $(seq 1 120); do
    if (echo > /dev/tcp/127.0.0.1/5432) 2>/dev/null; then break; fi
    sleep 0.5
done

# ============================================================================
# Shipped-tree facts — captured BEFORE any remediation touches the tree.
# ============================================================================

# Count the string-concatenation call sites in the shipped QueryService (each
# such site assembles its SQL into a local `String sql`).
CONCAT_SITES=$(grep -c 'String sql = ' "$JAVA_DIR/QueryService.java")

# Classify every dependency coordinate declared in the shipped pom against the
# offline station Maven repository: a coordinate is unresolvable if the repo
# has no such artifact, and noncompliant-resolvable if it resolves but the
# registry marks that version rescinded.
UNRESOLVABLE=0
NONCOMPLIANT_RESOLVABLE=0
while IFS='|' read -r g a v; do
    [ -z "$g" ] && continue
    if mvn -o -B -q org.apache.maven.plugins:maven-dependency-plugin:3.6.1:get \
            -Dartifact="$g:$a:$v" >/dev/null 2>&1; then
        st=$($PSQL -c "SELECT status FROM registry.artifact_review
            WHERE group_id='$g' AND artifact_id='$a' AND version='$v'")
        if [ "$st" = "rescinded" ]; then
            NONCOMPLIANT_RESOLVABLE=$((NONCOMPLIANT_RESOLVABLE + 1))
        fi
    else
        UNRESOLVABLE=$((UNRESOLVABLE + 1))
    fi
done < <(python3 - "$SVC/pom.xml" <<'PYX'
import re
import sys

txt = open(sys.argv[1]).read()
for dep in re.findall(r"<dependency>(.*?)</dependency>", txt, re.S):
    g = re.search(r"<groupId>(.*?)</groupId>", dep)
    a = re.search(r"<artifactId>(.*?)</artifactId>", dep)
    v = re.search(r"<version>(.*?)</version>", dep)
    if g and a and v:
        print(f"{g.group(1)}|{a.group(1)}|{v.group(1)}")
PYX
)

# ============================================================================
# Reconcile the decision record — registry (structured) + archive (prose).
# ============================================================================

# --- dependency approvals in force, from the registry -----------------------
JDBC_APPROVED=$($PSQL -c "SELECT version FROM registry.artifact_review
    WHERE group_id='org.postgresql' AND status='approved'")
MATH_GROUP=$($PSQL -c "SELECT group_id FROM registry.artifact_review
    WHERE artifact_id LIKE 'commons-math%' AND status='approved'")
MATH_ARTIFACT=$($PSQL -c "SELECT artifact_id FROM registry.artifact_review
    WHERE artifact_id LIKE 'commons-math%' AND status='approved'")
MATH_VERSION=$($PSQL -c "SELECT version FROM registry.artifact_review
    WHERE artifact_id LIKE 'commons-math%' AND status='approved'")
MATH_COORDINATE="${MATH_GROUP}:${MATH_ARTIFACT}:${MATH_VERSION}"
JSON_VERSION=$($PSQL -c "SELECT version FROM registry.artifact_review
    WHERE artifact_id='jackson-databind' AND status='approved'")
RESCINDED_JDBC=$($PSQL -c "SELECT string_agg(version, ',' ORDER BY
    string_to_array(version,'.')::int[]) FROM registry.artifact_review
    WHERE group_id='org.postgresql' AND status='rescinded'")
EVER_APPROVED=$($PSQL -c "SELECT count(*) FROM registry.artifact_review
    WHERE group_id='org.postgresql' AND minute_ref IS NOT NULL")
NEVER_APPROVED=$($PSQL -c "SELECT version FROM registry.artifact_review
    WHERE group_id='org.postgresql' AND status='noted_never_approved'")
EMERGENCY_APPLIED=$($PSQL -c "SELECT decided_on FROM registry.artifact_review
    WHERE status='noted_never_approved'")
RESCINDING_ADVISORY=$($PSQL -c "SELECT advisory_id FROM registry.advisory_register
    WHERE subject LIKE '%jdbc%'")
RESCINDING_ISSUED=$($PSQL -c "SELECT issued_on FROM registry.advisory_register
    WHERE subject LIKE '%jdbc%'")

# --- the JDBC approval whose minute document is absent from the archive ------
MISSING_MINUTE=""
for ref in $($PSQL -c "SELECT DISTINCT minute_ref FROM registry.artifact_review
        WHERE group_id='org.postgresql' AND minute_ref IS NOT NULL"); do
    if [ ! -f "$ARCH/minutes/${ref}.md" ]; then
        MISSING_MINUTE=$ref
    fi
done

# --- pom-revision history, from the engineering journals --------------------
# Each recorded revision carries a fixed recording sentence; a revert names
# itself on that same sentence.
POM_ENTRIES=$(grep -rl "A pom revision was recorded" "$ARCH/journal" | wc -l | tr -d ' ')
POM_REVERTED=$(grep -rhE "A pom revision was recorded:.*revert" "$ARCH/journal" \
    | wc -l | tr -d ' ')

# --- the commons-math 4.x disposition, from the governing minute ------------
MATH4_STATUS=$(grep -ioE 'migration question is (deferred|adopted|rejected)' \
    "$ARCH/minutes/DRB-2025-03.md" \
    | grep -ioE '(deferred|adopted|rejected)' | tr 'A-Z' 'a-z' | head -1)

# --- emergency-change dates: applied from the register, reverted day parsed
#     from the closing journal and combined with the applied month -----------
REVERT_DAY=$(grep -oE 'unwound on the ([0-9]+)th' "$ARCH/journal/J-2025-05b.md" \
    | grep -oE '[0-9]+')
EMERGENCY_REVERTED="${EMERGENCY_APPLIED%-*}-${REVERT_DAY}"

# --- bound-parameters mandate: the memo and its effective date --------------
MANDATE_FILE=$(grep -rl 'through bound parameters' "$ARCH/memos")
BINDING_MEMO=$(grep -oE 'M-[0-9]{4}-[0-9]+' "$MANDATE_FILE" | head -1)
BINDING_EFFECTIVE=$(grep -oE 'Effective [0-9]{4}-[0-9]{2}-[0-9]{2}' "$MANDATE_FILE" \
    | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}')

# --- the channel whose punctuation exposed the interpolation defect, and the
#     incident that first recorded it ----------------------------------------
QUOTED_CHANNEL=$($PSQL -c "SELECT DISTINCT channel FROM telemetry.readings
    WHERE channel LIKE '%''%'")
INCIDENT_FILE=$(grep -rl "$QUOTED_CHANNEL" "$ARCH/incidents")
QUOTED_INCIDENT=$(grep -oE 'INC-[0-9]{4}-[0-9]+' "$INCIDENT_FILE" | head -1)

# --- Station Systems Freeze date, from SOP-9 --------------------------------
FREEZE=$(grep -oE 'Freeze at ([0-9]{4}-[0-9]{2}-[0-9]{2})' \
    "$ARCH/sop/SOP-9_station_governance.md" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}')

# --- advisory reconciliation across register AND archive --------------------
ADV_TOTAL=$(grep -rhoE 'MRA-[0-9]{4}-[0-9]+' "$ARCH" | sort -u | wc -l | tr -d ' ')
ADV_REGISTERED=$($PSQL -c "SELECT count(*) FROM registry.advisory_register")
ADV_NEVER_REGISTERED=$((ADV_TOTAL - ADV_REGISTERED))
ADV_FOREIGN=$(grep -rhoE 'FHA-[0-9]{4}-[0-9]+' "$ARCH" | sort -u | wc -l | tr -d ' ')
ADV_IN_FORCE=$($PSQL -c "SELECT count(*) FROM registry.advisory_register
    WHERE issued_on <= DATE '$FREEZE'
      AND status NOT IN ('withdrawn','superseded','closed','pending')")

# ============================================================================
# Spectral method — trace the in-force revision, then parse its procedure.
# ============================================================================

# The erratum names the rescinded revision, the rescinding document, and the
# interim fallback.
ERRATUM_FILE=$(grep -rl 'rescinded in its entirety' "$ARCH/errata")
RESC_ERRATUM=$(grep -oE 'E-[0-9]{4}-[0-9]+' "$ERRATUM_FILE" | head -1)
RESC_REV=$(grep -oE 'Rescission of SMP-7 Revision ([A-Z])' "$ERRATUM_FILE" \
    | grep -oE '[A-Z]$')
FALLBACK_REV=$(grep -oE 'fallback is therefore revision ([A-Z])' "$ERRATUM_FILE" \
    | grep -oE '[A-Z]$')

# In-force revision at the freeze = the latest-adopted procedure that is
# neither the rescinded one nor adopted after the freeze.
ADOPTED_REV=""
ADOPTED_DATE=""
for f in "$ARCH"/sop/SMP-7_rev*.md; do
    rev=$(basename "$f" | grep -oE 'rev([A-Z])' | grep -oE '[A-Z]')
    [ "$rev" = "$RESC_REV" ] && continue
    d=$(grep -oE 'Adopted [0-9]{4}-[0-9]{2}-[0-9]{2}' "$f" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}')
    [ -z "$d" ] && continue
    [[ "$d" > "$FREEZE" ]] && continue
    if [ -z "$ADOPTED_DATE" ] || [[ "$d" > "$ADOPTED_DATE" ]]; then
        ADOPTED_DATE="$d"
        ADOPTED_REV="$rev"
    fi
done
SMP_FILE="$ARCH/sop/SMP-7_rev${ADOPTED_REV}.md"

# Parse the in-force procedure's numeric parameters and band table.
SEG_LEN=$(grep -oE 'segments of exactly ([0-9]+) samples' "$SMP_FILE" | grep -oE '[0-9]+')
SEG_HOP=$(grep -oE 'advances by ([0-9]+) samples' "$SMP_FILE" | grep -oE '[0-9]+')
BAND_COUNT=$(grep -cE '^\| [a-z_]+ +\| [0-9.]+ +\| [0-9]+ +\|' "$SMP_FILE")
BURST_LO=$(grep -E '^\| burst +\|' "$SMP_FILE" | grep -oE '[0-9]+' | head -1)
BURST_HI=$(grep -E '^\| burst +\|' "$SMP_FILE" | grep -oE '[0-9]+' | tail -1)
if grep -q 'sum of the squared window samples' "$SMP_FILE"; then
    WINDOW_NORM=sum_w_squared
elif grep -q 'plain segment-length denominator' "$SMP_FILE"; then
    WINDOW_NORM=segment_length
else
    WINDOW_NORM=squared_length
fi

# ============================================================================
# Remediation — repair the pom, the query layer, and the estimator.
# ============================================================================

cat > "$SVC/pom.xml" <<POM
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <groupId>org.mrgo</groupId>
  <artifactId>spectra-svc</artifactId>
  <version>1.4.1</version>
  <packaging>jar</packaging>

  <properties>
    <maven.compiler.release>21</maven.compiler.release>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
  </properties>

  <dependencies>
    <dependency>
      <groupId>org.postgresql</groupId>
      <artifactId>postgresql</artifactId>
      <version>${JDBC_APPROVED}</version>
    </dependency>
    <dependency>
      <groupId>${MATH_GROUP}</groupId>
      <artifactId>${MATH_ARTIFACT}</artifactId>
      <version>${MATH_VERSION}</version>
    </dependency>
    <dependency>
      <groupId>com.fasterxml.jackson.core</groupId>
      <artifactId>jackson-databind</artifactId>
      <version>${JSON_VERSION}</version>
    </dependency>
  </dependencies>

  <build>
    <finalName>spectra-svc</finalName>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-compiler-plugin</artifactId>
        <version>3.13.0</version>
      </plugin>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-jar-plugin</artifactId>
        <version>3.4.1</version>
        <configuration>
          <archive>
            <manifest>
              <mainClass>org.mrgo.spectra.SpectraServer</mainClass>
              <addClasspath>true</addClasspath>
              <classpathPrefix>lib/</classpathPrefix>
            </manifest>
          </archive>
        </configuration>
      </plugin>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-dependency-plugin</artifactId>
        <version>3.6.1</version>
        <executions>
          <execution>
            <id>copy-runtime-deps</id>
            <phase>package</phase>
            <goals>
              <goal>copy-dependencies</goal>
            </goals>
            <configuration>
              <outputDirectory>\${project.build.directory}/lib</outputDirectory>
              <includeScope>runtime</includeScope>
            </configuration>
          </execution>
        </executions>
      </plugin>
    </plugins>
  </build>
</project>
POM

cat > "$JAVA_DIR/QueryService.java" <<'JAVA'
package org.mrgo.spectra;

import java.sql.Array;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;

/** Data access for telemetry frames stored in the meridian database. */
public final class QueryService {

    public static final int SAMPLE_RATE_HZ = 512;

    private static final String URL =
            System.getenv().getOrDefault(
                    "MERIDIAN_DB_URL",
                    "jdbc:postgresql://127.0.0.1:5432/meridian?user=meridian");

    private Connection connect() throws SQLException {
        return DriverManager.getConnection(URL);
    }

    /** Distinct channel identifiers, sorted. Constant SQL, no request input. */
    public List<String> listChannels() throws SQLException {
        List<String> out = new ArrayList<>();
        try (Connection conn = connect();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(
                     "SELECT DISTINCT channel FROM telemetry.readings ORDER BY channel")) {
            while (rs.next()) {
                out.add(rs.getString(1));
            }
        }
        return out;
    }

    /** Sample frames for a channel captured within [from, to). */
    public List<double[]> fetchFrames(String channel, String from, String to) throws SQLException {
        String sql = "SELECT samples FROM telemetry.readings"
                + " WHERE channel = ? AND captured_at >= ? AND captured_at < ?"
                + " ORDER BY captured_at";
        List<double[]> out = new ArrayList<>();
        try (Connection conn = connect();
             PreparedStatement stmt = conn.prepareStatement(sql)) {
            stmt.setString(1, channel);
            stmt.setObject(2, OffsetDateTime.parse(from));
            stmt.setObject(3, OffsetDateTime.parse(to));
            try (ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    Array arr = rs.getArray(1);
                    Double[] boxed = (Double[]) arr.getArray();
                    double[] frame = new double[boxed.length];
                    for (int i = 0; i < boxed.length; i++) {
                        frame[i] = boxed[i];
                    }
                    out.add(frame);
                }
            }
        }
        return out;
    }

    /** Total frames recorded for a channel. */
    public long frameCount(String channel) throws SQLException {
        String sql = "SELECT count(*) FROM telemetry.readings WHERE channel = ?";
        try (Connection conn = connect();
             PreparedStatement stmt = conn.prepareStatement(sql)) {
            stmt.setString(1, channel);
            try (ResultSet rs = stmt.executeQuery()) {
                rs.next();
                return rs.getLong(1);
            }
        }
    }

    /** Most recent capture timestamp for a channel, as text. */
    public String latestCapture(String channel) throws SQLException {
        String sql = "SELECT max(captured_at) FROM telemetry.readings WHERE channel = ?";
        try (Connection conn = connect();
             PreparedStatement stmt = conn.prepareStatement(sql)) {
            stmt.setString(1, channel);
            try (ResultSet rs = stmt.executeQuery()) {
                rs.next();
                return rs.getString(1);
            }
        }
    }
}
JAVA

cat > "$JAVA_DIR/Welch.java" <<'JAVA'
package org.mrgo.spectra;

import org.apache.commons.math3.complex.Complex;
import org.apache.commons.math3.transform.DftNormalization;
import org.apache.commons.math3.transform.FastFourierTransformer;
import org.apache.commons.math3.transform.TransformType;

/** Averaged-periodogram power spectral density estimation, SMP-7 revision D. */
public final class Welch {

    public static final int SEGMENT_LENGTH = 1024;
    public static final int SEGMENT_HOP = 512;

    private Welch() {
    }

    /**
     * One-sided PSD of a frame, averaged over half-overlapped, detrended,
     * symmetric-Hann-windowed segments, scaled by fs times the window energy.
     * Returns L/2 + 1 bins for segment length L.
     */
    public static double[] powerSpectralDensity(double[] frame, int sampleRateHz) {
        int seg = SEGMENT_LENGTH;
        int hop = SEGMENT_HOP;
        double[] window = new double[seg];
        double sumW2 = 0.0;
        for (int i = 0; i < seg; i++) {
            window[i] = 0.5 * (1.0 - Math.cos(2.0 * Math.PI * i / (double) (seg - 1)));
            sumW2 += window[i] * window[i];
        }

        FastFourierTransformer fft = new FastFourierTransformer(DftNormalization.STANDARD);
        int bins = seg / 2 + 1;
        double[] psd = new double[bins];
        int segments = 0;

        for (int start = 0; start + seg <= frame.length; start += hop) {
            double mean = 0.0;
            for (int i = 0; i < seg; i++) {
                mean += frame[start + i];
            }
            mean /= seg;
            double[] buf = new double[seg];
            for (int i = 0; i < seg; i++) {
                buf[i] = (frame[start + i] - mean) * window[i];
            }
            Complex[] spectrum = fft.transform(buf, TransformType.FORWARD);
            double scale = 2.0 / (sampleRateHz * sumW2);
            for (int k = 0; k < bins; k++) {
                double mag2 = spectrum[k].abs() * spectrum[k].abs();
                double value = scale * mag2;
                if (k == 0 || k == seg / 2) {
                    value /= 2.0;
                }
                psd[k] += value;
            }
            segments++;
        }

        for (int k = 0; k < bins; k++) {
            psd[k] /= segments;
        }
        return psd;
    }
}
JAVA

cat > "$JAVA_DIR/Bands.java" <<'JAVA'
package org.mrgo.spectra;

/** Frequency band table and band-power integration, SMP-7 revision D. */
public final class Bands {

    public record Band(String name, double loHz, double hiHz) {
    }

    public static final Band[] TABLE = {
            new Band("quiet", 0.5, 8.0),
            new Band("pulse_low", 8.0, 24.0),
            new Band("pulse_mid", 24.0, 64.0),
            new Band("pulse_high", 64.0, 128.0),
            new Band("burst", 128.0, 224.0),
    };

    private Bands() {
    }

    /** Integrates PSD bins whose exact frequency falls in the half-open band. */
    public static double bandPower(double[] psd, Band band, int sampleRateHz, int segmentLength) {
        double df = (double) sampleRateHz / segmentLength;
        double power = 0.0;
        for (int k = 0; k < psd.length; k++) {
            double f = k * df;
            if (f >= band.loHz() && f < band.hiHz()) {
                power += psd[k] * df;
            }
        }
        return power;
    }
}
JAVA

# Report the in-force revision letter derived above.
sed -i "s/body.put(\"revision\", \"C\");/body.put(\"revision\", \"${ADOPTED_REV}\");/" \
    "$JAVA_DIR/SpectraServer.java"

# ------------------------------------------------------------- offline build
cd "$SVC"
mvn -o -B -q -DskipTests package
test -f "$SVC/target/spectra-svc.jar"

# ------------------------------------------------------- endpoint smoke check
java -jar "$SVC/target/spectra-svc.jar" &
SVC_PID=$!
for _ in $(seq 1 120); do
    if (echo > /dev/tcp/127.0.0.1/8747) 2>/dev/null; then break; fi
    sleep 0.5
done
curl -fsS "http://127.0.0.1:8747/health" > /dev/null
curl -fsS "http://127.0.0.1:8747/channels" > /dev/null
curl -fsS -G "http://127.0.0.1:8747/bandpower" \
    --data-urlencode "channel=$QUOTED_CHANNEL" \
    --data-urlencode "from=2025-11-14T00:00:00Z" \
    --data-urlencode "to=2025-11-14T00:02:00Z" > /dev/null
kill "$SVC_PID"
wait "$SVC_PID" 2>/dev/null || true

# ============================================================================
# File the dossier — assembled entirely from the derived values above.
# ============================================================================
mkdir -p /app/audit
export JDBC_APPROVED RESCINDED_JDBC RESCINDING_ADVISORY RESCINDING_ISSUED \
    EVER_APPROVED MISSING_MINUTE NEVER_APPROVED EMERGENCY_APPLIED \
    EMERGENCY_REVERTED MATH_COORDINATE MATH4_STATUS JSON_VERSION UNRESOLVABLE \
    NONCOMPLIANT_RESOLVABLE POM_ENTRIES POM_REVERTED BINDING_MEMO \
    BINDING_EFFECTIVE CONCAT_SITES QUOTED_CHANNEL QUOTED_INCIDENT ADOPTED_REV \
    RESC_REV RESC_ERRATUM FALLBACK_REV BAND_COUNT BURST_LO BURST_HI SEG_LEN \
    SEG_HOP WINDOW_NORM ADV_TOTAL ADV_REGISTERED ADV_NEVER_REGISTERED \
    ADV_IN_FORCE ADV_FOREIGN FREEZE
python3 - <<'PY'
import json
import os

e = os.environ
dossier = {
    "build_provenance": {
        "approved_jdbc_version": e["JDBC_APPROVED"],
        "rescinded_jdbc_versions": e["RESCINDED_JDBC"].split(","),
        "rescinding_advisory": e["RESCINDING_ADVISORY"],
        "rescinding_advisory_issued": e["RESCINDING_ISSUED"],
        "jdbc_versions_ever_board_approved": int(e["EVER_APPROVED"]),
        "jdbc_approval_missing_minute": e["MISSING_MINUTE"],
        "emergency_jdbc_version_never_approved": e["NEVER_APPROVED"],
        "emergency_change_applied_on": e["EMERGENCY_APPLIED"],
        "emergency_change_reverted_on": e["EMERGENCY_REVERTED"],
        "math_library_coordinate": e["MATH_COORDINATE"],
        "math4_migration_status": e["MATH4_STATUS"],
        "json_library_version": e["JSON_VERSION"],
        "unresolvable_coordinates_count": int(e["UNRESOLVABLE"]),
        "noncompliant_resolvable_coordinates_count": int(e["NONCOMPLIANT_RESOLVABLE"]),
        "pom_revision_entries_recorded": int(e["POM_ENTRIES"]),
        "pom_revisions_reverted_count": int(e["POM_REVERTED"]),
    },
    "query_compliance": {
        "binding_mandate_memo": e["BINDING_MEMO"],
        "binding_mandate_effective": e["BINDING_EFFECTIVE"],
        "concat_call_sites_in_query_service": int(e["CONCAT_SITES"]),
        "quoted_channel_identifier": e["QUOTED_CHANNEL"],
        "quoted_channel_incident": e["QUOTED_INCIDENT"],
    },
    "spectral_method": {
        "adopted_smp_revision": e["ADOPTED_REV"],
        "rescinded_smp_revision": e["RESC_REV"],
        "rescinding_erratum": e["RESC_ERRATUM"],
        "interim_fallback_revision": e["FALLBACK_REV"],
        "band_count_adopted": int(e["BAND_COUNT"]),
        "burst_band_bounds_hz": [float(e["BURST_LO"]), float(e["BURST_HI"])],
        "segment_length": int(e["SEG_LEN"]),
        "segment_hop": int(e["SEG_HOP"]),
        "window_normalization": e["WINDOW_NORM"],
    },
    "registry_reconciliation": {
        "advisories_total_recorded": int(e["ADV_TOTAL"]),
        "advisories_registered_in_db": int(e["ADV_REGISTERED"]),
        "advisories_never_registered": int(e["ADV_NEVER_REGISTERED"]),
        "advisories_in_force_at_freeze": int(e["ADV_IN_FORCE"]),
        "foreign_advisories_cited": int(e["ADV_FOREIGN"]),
        "audit_freeze_date": e["FREEZE"],
    },
}
with open("/app/audit/provenance_dossier.json", "w") as fh:
    json.dump(dossier, fh, indent=2)
    fh.write("\n")
PY

echo "oracle complete"
