package org.terminus.calc;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import static org.terminus.calc.Model.*;

final class ResultWriter {
    static String render(Recovered recovered, AnalysisData analysis) {
        StringBuilder out = new StringBuilder();
        Meta meta = recovered.state.meta;
        out.append('{');
        keyValue(out, "schema", REPORT_SCHEMA).append(',');
        out.append("\"simulation\":{")
            .append("\"dimensions\":3,\"dt\":").append(f9(meta.dt))
            .append(",\"boxLength\":").append(f9(meta.box))
            .append(",\"particles\":[");
        for (int i = 0; i < meta.particles.size(); i++) {
            if (i > 0) out.append(',');
            string(out, meta.particles.get(i));
        }
        out.append("],\"fitLagStart\":").append(meta.fitStart)
            .append(",\"fitLagEnd\":").append(meta.fitEnd).append("},");

        Counts counts = recovered.counts;
        out.append("\"recovery\":{")
            .append("\"shardsSeen\":").append(counts.shardsSeen)
            .append(",\"recordsSeen\":").append(counts.recordsSeen)
            .append(",\"recordsValid\":").append(counts.recordsValid)
            .append(",\"recordsRejectedMalformed\":").append(counts.malformed)
            .append(",\"recordsRejectedCrc\":").append(counts.crc)
            .append(",\"recordsRejectedUnknownParticle\":").append(counts.unknown)
            .append(",\"supersededDiscarded\":").append(counts.superseded)
            .append(",\"duplicatesDiscarded\":").append(counts.duplicates)
            .append(",\"conflictingKeys\":").append(counts.conflicts)
            .append(",\"shardsApplied\":[");
        for (int i = 0; i < recovered.state.shards.size(); i++) {
            if (i > 0) out.append(',');
            Shard shard = recovered.state.shards.get(i);
            out.append("{\"id\":");
            string(out, shard.id);
            out.append(",\"generation\":").append(shard.generation)
                .append(",\"records\":").append(shard.records.size())
                .append(",\"sha256\":");
            string(out, shard.sha256);
            out.append('}');
        }
        out.append("],\"completeTimesteps\":[");
        for (int i = 0; i < recovered.complete.size(); i++) {
            if (i > 0) out.append(',');
            out.append(recovered.complete.get(i));
        }
        out.append("],\"rejectedTimesteps\":[");
        for (int i = 0; i < recovered.rejected.size(); i++) {
            if (i > 0) out.append(',');
            Reject reject = recovered.rejected.get(i);
            out.append("{\"tick\":").append(reject.tick).append(",\"reason\":");
            string(out, reject.reason);
            out.append('}');
        }
        out.append("]},");
        keyValue(out, "sourceSha256", recovered.state.sourceHash).append(',');
        keyValue(out, "stateSha256", recovered.state.stateHash).append(',');
        keyValue(out, "datasetSha256", analysis.datasetHash).append(',');

        out.append("\"msd\":[");
        for (int i = 0; i < analysis.msd.size(); i++) {
            if (i > 0) out.append(',');
            Msd row = analysis.msd.get(i);
            out.append("{\"lag\":").append(row.lag)
                .append(",\"time\":").append(f9(row.time))
                .append(",\"pairs\":").append(row.pairs)
                .append(",\"msdX\":").append(f9(row.x))
                .append(",\"msdY\":").append(f9(row.y))
                .append(",\"msdZ\":").append(f9(row.z))
                .append(",\"msdTotal\":").append(f9(row.total)).append('}');
        }
        Reg regression = analysis.regression;
        out.append("],\"regression\":{\"lagsUsed\":[");
        for (int i = 0; i < regression.lags.size(); i++) {
            if (i > 0) out.append(',');
            out.append(regression.lags.get(i));
        }
        out.append("],\"slope\":").append(f9(regression.slope))
            .append(",\"intercept\":").append(f9(regression.intercept))
            .append(",\"rSquared\":").append(f9(regression.r2))
            .append(",\"slopeStdErr\":").append(f9(regression.stderr))
            .append(",\"diffusionCoefficient\":").append(f9(regression.diffusion))
            .append(",\"diffusionStdErr\":").append(f9(regression.diffusionErr))
            .append(",\"axisDiffusion\":{\"x\":").append(f9(regression.axisX))
            .append(",\"y\":").append(f9(regression.axisY))
            .append(",\"z\":").append(f9(regression.axisZ)).append("}}}\n");
        return out.toString();
    }

    static void publish(Path statePath, boolean writeState, Path dbPath, Path reportPath,
                        StateData state, Recovered recovered, AnalysisData analysis, String reportText)
        throws Exception {
        List<Path> targets = new ArrayList<>();
        if (writeState) targets.add(normalize(statePath));
        targets.add(normalize(dbPath));
        targets.add(normalize(reportPath));
        if (new HashSet<>(targets).size() != targets.size()) throw new Validation("output paths must be distinct");
        for (Path target : targets) {
            if (Files.isDirectory(target)) throw new java.io.IOException("output path is directory");
            Files.createDirectories(target.getParent());
        }

        String token = UUID.randomUUID().toString();
        Map<Path, Path> temporary = new HashMap<>();
        Map<Path, Path> backup = new HashMap<>();
        Set<Path> installed = new HashSet<>();
        try {
            if (writeState) {
                Path target = normalize(statePath);
                Path temp = temp(target, token, "state");
                Files.writeString(temp, state.text, StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
                temporary.put(target, temp);
            }
            Path dbTarget = normalize(dbPath);
            Path dbTemp = temp(dbTarget, token, "db");
            DatabaseLoader.write(dbTemp, recovered, analysis);
            temporary.put(dbTarget, dbTemp);
            Path reportTarget = normalize(reportPath);
            Path reportTemp = temp(reportTarget, token, "report");
            Files.writeString(reportTemp, reportText, StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
            temporary.put(reportTarget, reportTemp);

            for (Path target : targets) {
                if (Files.exists(target)) {
                    Path old = temp(target, token, "backup");
                    move(target, old);
                    backup.put(target, old);
                }
            }
            for (Path target : targets) {
                move(temporary.get(target), target);
                installed.add(target);
            }
            for (Path old : backup.values()) Files.deleteIfExists(old);
        } catch (Exception failure) {
            for (Path target : installed) Files.deleteIfExists(target);
            for (Map.Entry<Path, Path> entry : backup.entrySet()) {
                if (Files.exists(entry.getValue())) move(entry.getValue(), entry.getKey());
            }
            throw failure;
        } finally {
            for (Path path : temporary.values()) Files.deleteIfExists(path);
            for (Path path : backup.values()) Files.deleteIfExists(path);
        }
    }

    private static Path normalize(Path path) {
        return path.toAbsolutePath().normalize();
    }

    private static Path temp(Path target, String token, String kind) {
        return target.getParent().resolve("." + target.getFileName() + "." + token + "." + kind + ".tmp");
    }

    private static void move(Path from, Path to) throws Exception {
        Files.move(from, to, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
    }

    private static StringBuilder keyValue(StringBuilder out, String key, String value) {
        out.append('"').append(key).append("\":");
        string(out, value);
        return out;
    }

    private static void string(StringBuilder out, String value) {
        out.append('"');
        for (char c : value.toCharArray()) {
            if (c == '"' || c == '\\') out.append('\\').append(c);
            else if (c < 32) out.append(String.format("\\u%04x", (int) c));
            else out.append(c);
        }
        out.append('"');
    }

    private static String f9(double value) {
        if (value == 0.0d) value = 0.0d;
        return BigDecimal.valueOf(value).setScale(9, RoundingMode.HALF_UP).toPlainString();
    }

    private ResultWriter() {}
}
