package com.foldlab.balance;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

public final class SkewBandClassifier {
    public String classify(double maxLabelSkew) {
        if (maxLabelSkew < 0.05) {
            return "tight";
        }
        if (maxLabelSkew < 0.15) {
            return "moderate";
        }
        return "loose";
    }

    public String bandAnchor(String skewBand, String foldDigest) {
        return sha256Hex(skewBand + "|" + foldDigest);
    }

    private static String sha256Hex(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(hash.length * 2);
            for (byte b : hash) {
                hex.append(String.format("%02x", b));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }
}
