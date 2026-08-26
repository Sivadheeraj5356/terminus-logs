package org.terminus.calc;

import java.util.List;

final class Model {
    static final String REPORT_SCHEMA = "brownian-diffusion-report/v2";
    static final String STATE_SCHEMA = "brownian-recovery-state/v2";

    static final class Validation extends Exception {
        Validation(String message) { super(message); }
    }

    static final class Insufficient extends Exception {
        Insufficient(String message) { super(message); }
    }

    static final class StateMismatch extends Exception {
        StateMismatch(String message) { super(message); }
    }

    static final class Meta {
        final double dt;
        final double box;
        final List<String> particles;
        final int fitStart;
        final int fitEnd;

        Meta(double dt, double box, List<String> particles, int fitStart, int fitEnd) {
            this.dt = dt;
            this.box = box;
            this.particles = particles;
            this.fitStart = fitStart;
            this.fitEnd = fitEnd;
        }
    }

    static final class Shard {
        final String id;
        final long generation;
        final List<String> records;
        final String sha256;

        Shard(String id, long generation, List<String> records, String sha256) {
            this.id = id;
            this.generation = generation;
            this.records = records;
            this.sha256 = sha256;
        }
    }

    static final class StateData {
        final Meta meta;
        final List<Shard> shards;
        final String sourceHash;
        final String stateHash;
        final String text;

        StateData(Meta meta, List<Shard> shards, String sourceHash, String stateHash, String text) {
            this.meta = meta;
            this.shards = shards;
            this.sourceHash = sourceHash;
            this.stateHash = stateHash;
            this.text = text;
        }
    }

    static final class Row {
        final long tick;
        final String particle;
        final double x;
        final double y;
        final double z;
        final long generation;
        final String shard;

        Row(long tick, String particle, double x, double y, double z, long generation, String shard) {
            this.tick = tick;
            this.particle = particle;
            this.x = x;
            this.y = y;
            this.z = z;
            this.generation = generation;
            this.shard = shard;
        }
    }

    static final class Reject {
        final long tick;
        final String reason;

        Reject(long tick, String reason) {
            this.tick = tick;
            this.reason = reason;
        }
    }

    static final class Counts {
        int shardsSeen;
        int recordsSeen;
        int recordsValid;
        int malformed;
        int crc;
        int unknown;
        int superseded;
        int duplicates;
        int conflicts;
    }

    static final class Recovered {
        final StateData state;
        final Counts counts;
        final List<Row> selected;
        final List<Long> complete;
        final List<Reject> rejected;

        Recovered(StateData state, Counts counts, List<Row> selected, List<Long> complete, List<Reject> rejected) {
            this.state = state;
            this.counts = counts;
            this.selected = selected;
            this.complete = complete;
            this.rejected = rejected;
        }
    }

    static final class Point {
        final long segment;
        final long tick;
        final String particle;
        final double x;
        final double y;
        final double z;
        final double ux;
        final double uy;
        final double uz;
        final double driftX;
        final double driftY;
        final double driftZ;

        Point(long segment, long tick, String particle, double x, double y, double z,
              double ux, double uy, double uz, double driftX, double driftY, double driftZ) {
            this.segment = segment;
            this.tick = tick;
            this.particle = particle;
            this.x = x;
            this.y = y;
            this.z = z;
            this.ux = ux;
            this.uy = uy;
            this.uz = uz;
            this.driftX = driftX;
            this.driftY = driftY;
            this.driftZ = driftZ;
        }
    }

    static final class Msd {
        final int lag;
        final double time;
        final long pairs;
        final double x;
        final double y;
        final double z;
        final double total;

        Msd(int lag, double time, long pairs, double x, double y, double z, double total) {
            this.lag = lag;
            this.time = time;
            this.pairs = pairs;
            this.x = x;
            this.y = y;
            this.z = z;
            this.total = total;
        }
    }

    static final class Reg {
        final List<Integer> lags;
        final double slope;
        final double intercept;
        final double r2;
        final double stderr;
        final double diffusion;
        final double diffusionErr;
        final double axisX;
        final double axisY;
        final double axisZ;

        Reg(List<Integer> lags, double slope, double intercept, double r2, double stderr,
            double diffusion, double diffusionErr, double axisX, double axisY, double axisZ) {
            this.lags = lags;
            this.slope = slope;
            this.intercept = intercept;
            this.r2 = r2;
            this.stderr = stderr;
            this.diffusion = diffusion;
            this.diffusionErr = diffusionErr;
            this.axisX = axisX;
            this.axisY = axisY;
            this.axisZ = axisZ;
        }
    }

    static final class AnalysisData {
        final List<Point> points;
        final List<Msd> msd;
        final Reg regression;
        final String datasetHash;

        AnalysisData(List<Point> points, List<Msd> msd, Reg regression, String datasetHash) {
            this.points = points;
            this.msd = msd;
            this.regression = regression;
            this.datasetHash = datasetHash;
        }
    }

    private Model() {}
}
