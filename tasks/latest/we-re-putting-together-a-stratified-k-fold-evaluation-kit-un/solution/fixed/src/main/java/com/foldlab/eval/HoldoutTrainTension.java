package com.foldlab.eval;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

public final class HoldoutTrainTension {
    public String compute(
            String trainFoldMask,
            String holdoutExclusionSeal,
            String holdoutEpochCoupler,
            int foldLoadSkew) {
        String body = trainFoldMask + "|" + holdoutExclusionSeal + "|" + holdoutEpochCoupler + "|" + foldLoadSkew;
        return sha256Hex(body);
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

