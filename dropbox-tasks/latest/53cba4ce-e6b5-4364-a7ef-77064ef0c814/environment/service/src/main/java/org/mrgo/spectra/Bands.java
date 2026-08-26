package org.mrgo.spectra;

/** Frequency band table and band-power integration for reporting. */
public final class Bands {

    public record Band(String name, double loHz, double hiHz) {
    }

    public static final Band[] TABLE = {
            new Band("quiet", 0.5, 8.0),
            new Band("pulse_low", 8.0, 24.0),
            new Band("pulse_mid", 24.0, 64.0),
            new Band("pulse_high", 64.0, 128.0),
            new Band("burst", 128.0, 224.0),
            new Band("guard", 224.0, 256.0),
    };

    private Bands() {
    }

    /** Integrates PSD bins whose frequency falls in the band. */
    public static double bandPower(double[] psd, Band band, int sampleRateHz, int segmentLength) {
        double df = (double) sampleRateHz / segmentLength;
        double power = 0.0;
        for (int k = 0; k < psd.length; k++) {
            double f = Math.round(k * df * 10.0) / 10.0;
            if (f >= band.loHz() && f <= band.hiHz()) {
                power += psd[k] * df;
            }
        }
        return power;
    }
}
