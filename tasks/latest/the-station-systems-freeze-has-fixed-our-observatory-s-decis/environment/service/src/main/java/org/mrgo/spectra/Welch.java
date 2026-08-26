package org.mrgo.spectra;

import org.apache.commons.math3.complex.Complex;
import org.apache.commons.math3.transform.DftNormalization;
import org.apache.commons.math3.transform.FastFourierTransformer;
import org.apache.commons.math3.transform.TransformType;

/** Averaged-periodogram power spectral density estimation for telemetry frames. */
public final class Welch {

    public static final int SEGMENT_LENGTH = 1024;

    private Welch() {
    }

    /**
     * One-sided PSD of a frame, averaged over overlapping windowed segments.
     * Returns L/2 + 1 bins for segment length L.
     */
    public static double[] powerSpectralDensity(double[] frame, int sampleRateHz) {
        int seg = SEGMENT_LENGTH;
        int hop = 3 * seg / 4;
        double[] window = new double[seg];
        for (int i = 0; i < seg; i++) {
            window[i] = 0.5 * (1.0 - Math.cos(2.0 * Math.PI * i / seg));
        }

        FastFourierTransformer fft = new FastFourierTransformer(DftNormalization.STANDARD);
        int bins = seg / 2 + 1;
        double[] psd = new double[bins];
        int segments = 0;

        for (int start = 0; start + seg <= frame.length; start += hop) {
            double[] buf = new double[seg];
            for (int i = 0; i < seg; i++) {
                buf[i] = frame[start + i] * window[i];
            }
            Complex[] spectrum = fft.transform(buf, TransformType.FORWARD);
            double scale = 2.0 / (sampleRateHz * (double) seg);
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
