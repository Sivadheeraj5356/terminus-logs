package org.terminus.calc;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import static org.terminus.calc.Model.*;

final class Dynamics {
    static AnalysisData compute(Recovered recovered) throws Insufficient {
        Meta meta = recovered.state.meta;
        Map<String, Row> selected = new HashMap<>();
        for (Row row : recovered.selected) selected.put(key(row.tick, row.particle), row);

        List<List<Long>> segments = new ArrayList<>();
        List<Long> current = new ArrayList<>();
        for (long tick : recovered.complete) {
            if (!current.isEmpty() && tick != current.get(current.size() - 1) + 1) {
                segments.add(current);
                current = new ArrayList<>();
            }
            current.add(tick);
        }
        if (!current.isEmpty()) segments.add(current);

        List<Point> points = new ArrayList<>();
        Map<Long, Map<String, double[]>> unwrapped = new HashMap<>();
        for (int segmentId = 0; segmentId < segments.size(); segmentId++) {
            List<Long> segment = segments.get(segmentId);
            Map<String, double[]> u = new HashMap<>();
            for (String particle : meta.particles) u.put(particle, new double[] {0, 0, 0});
            for (int index = 0; index < segment.size(); index++) {
                long tick = segment.get(index);
                double[] drift = new double[] {0, 0, 0};
                if (index > 0) {
                    long previousTick = segment.get(index - 1);
                    Map<String, double[]> steps = new HashMap<>();
                    for (String particle : meta.particles) {
                        Row before = selected.get(key(previousTick, particle));
                        Row after = selected.get(key(tick, particle));
                        double[] step = new double[] {
                            minimumImage(after.x - before.x, meta.box),
                            minimumImage(after.y - before.y, meta.box),
                            minimumImage(after.z - before.z, meta.box)
                        };
                        steps.put(particle, step);
                        for (int axis = 0; axis < 3; axis++) drift[axis] += step[axis];
                    }
                    for (int axis = 0; axis < 3; axis++) drift[axis] /= meta.particles.size();
                    for (String particle : meta.particles) {
                        double[] point = u.get(particle);
                        double[] step = steps.get(particle);
                        for (int axis = 0; axis < 3; axis++) point[axis] += step[axis] - drift[axis];
                    }
                }
                Map<String, double[]> tickPositions = new HashMap<>();
                for (String particle : meta.particles) {
                    double[] position = u.get(particle).clone();
                    tickPositions.put(particle, position);
                    Row row = selected.get(key(tick, particle));
                    points.add(new Point(segmentId, tick, particle, row.x, row.y, row.z,
                        position[0], position[1], position[2], drift[0], drift[1], drift[2]));
                }
                unwrapped.put(tick, tickPositions);
            }
        }

        List<Msd> msd = new ArrayList<>();
        for (int lag = 1; lag <= meta.fitEnd; lag++) {
            double sumX = 0;
            double sumY = 0;
            double sumZ = 0;
            long pairs = 0;
            for (List<Long> segment : segments) {
                Set<Long> ticks = new HashSet<>(segment);
                for (long tick : segment) {
                    if (!ticks.contains(tick + lag)) continue;
                    for (String particle : meta.particles) {
                        double[] before = unwrapped.get(tick).get(particle);
                        double[] after = unwrapped.get(tick + lag).get(particle);
                        double dx = after[0] - before[0];
                        double dy = after[1] - before[1];
                        double dz = after[2] - before[2];
                        sumX += dx * dx;
                        sumY += dy * dy;
                        sumZ += dz * dz;
                        pairs++;
                    }
                }
            }
            if (pairs > 0) {
                msd.add(new Msd(lag, lag * meta.dt, pairs, sumX / pairs, sumY / pairs, sumZ / pairs,
                    (sumX + sumY + sumZ) / pairs));
            }
        }

        List<Msd> fit = new ArrayList<>();
        for (Msd row : msd) if (row.lag >= meta.fitStart && row.lag <= meta.fitEnd) fit.add(row);
        if (fit.size() < 3) throw new Insufficient("insufficient fitted lags");
        Fit total = regress(fit, Axis.TOTAL);
        Fit x = regress(fit, Axis.X);
        Fit y = regress(fit, Axis.Y);
        Fit z = regress(fit, Axis.Z);
        List<Integer> lags = fit.stream().map(row -> row.lag).toList();
        Reg regression = new Reg(lags, total.slope, total.intercept, total.r2, total.stderr,
            total.slope / 6.0, total.stderr / 6.0, x.slope / 2.0, y.slope / 2.0, z.slope / 2.0);

        Set<Long> complete = new HashSet<>(recovered.complete);
        StringBuilder preimage = new StringBuilder();
        for (Row row : recovered.selected) {
            if (complete.contains(row.tick)) {
                preimage.append(row.tick).append('|').append(row.particle).append('|')
                    .append(StateStore.canonicalNumber(row.x)).append('|')
                    .append(StateStore.canonicalNumber(row.y)).append('|')
                    .append(StateStore.canonicalNumber(row.z)).append('\n');
            }
        }
        String datasetHash = StateStore.sha256(preimage.toString().getBytes(StandardCharsets.UTF_8));
        return new AnalysisData(List.copyOf(points), List.copyOf(msd), regression, datasetHash);
    }

    private enum Axis { X, Y, Z, TOTAL }

    private record Fit(double slope, double intercept, double r2, double stderr) {}

    private static Fit regress(List<Msd> rows, Axis axis) {
        int n = rows.size();
        double meanX = 0;
        double meanY = 0;
        for (Msd row : rows) {
            meanX += row.time;
            meanY += value(row, axis);
        }
        meanX /= n;
        meanY /= n;
        double sxx = 0;
        double covariance = 0;
        for (Msd row : rows) {
            sxx += square(row.time - meanX);
            covariance += (row.time - meanX) * (value(row, axis) - meanY);
        }
        double slope = covariance / sxx;
        double intercept = meanY - slope * meanX;
        double sse = 0;
        double sst = 0;
        for (Msd row : rows) {
            double y = value(row, axis);
            sse += square(y - (intercept + slope * row.time));
            sst += square(y - meanY);
        }
        double r2 = sst == 0 ? (sse == 0 ? 1 : 0) : 1 - sse / sst;
        double stderr = Math.sqrt((sse / (n - 2)) / sxx);
        return new Fit(slope, intercept, r2, stderr);
    }

    private static double value(Msd row, Axis axis) {
        return switch (axis) {
            case X -> row.x;
            case Y -> row.y;
            case Z -> row.z;
            case TOTAL -> row.total;
        };
    }

    private static double minimumImage(double delta, double box) {
        while (delta > box / 2.0) delta -= box;
        while (delta <= -box / 2.0) delta += box;
        return delta;
    }

    private static double square(double value) {
        return value * value;
    }

    private static String key(long tick, String particle) {
        return tick + "\u0000" + particle;
    }

    private Dynamics() {}
}
