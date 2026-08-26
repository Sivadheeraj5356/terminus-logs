package com.foldlab.digest;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

public final class LedgerCoupler {
    public String epochSeal(int rotationEpoch, String manifestSeal) {
        return sha256Hex(rotationEpoch + "|" + manifestSeal);
    }

    public String ledgerRoot(String stagedFingerprint, String cohortChecksum, String epochSeal) {
        return sha256Hex(stagedFingerprint + "|" + cohortChecksum + "|" + epochSeal);
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
