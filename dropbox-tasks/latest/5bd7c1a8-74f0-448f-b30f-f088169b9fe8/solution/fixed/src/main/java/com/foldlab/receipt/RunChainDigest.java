package com.foldlab.receipt;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.List;

public final class RunChainDigest {
    public String compute(String kitClosure, Path receiptPath) throws IOException {
        String previous = "GENESIS";
        if (Files.exists(receiptPath)) {
            List<String> lines = Files.readAllLines(receiptPath);
            for (int index = lines.size() - 1; index >= 0; index--) {
                String line = lines.get(index).trim();
                if (line.isEmpty()) {
                    continue;
                }
                JsonObject record = JsonParser.parseString(line).getAsJsonObject();
                if (record.has("run_chain_digest")) {
                    previous = record.get("run_chain_digest").getAsString();
                }
                break;
            }
        }
        return sha256Hex(previous + "|" + kitClosure);
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
