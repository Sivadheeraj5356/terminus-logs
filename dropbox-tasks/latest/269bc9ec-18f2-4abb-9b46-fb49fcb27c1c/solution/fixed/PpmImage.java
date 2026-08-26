package org.example.parity;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

record PpmImage(int width, int height, int maxValue, int[] samples) {
    static PpmImage read(Path path) throws IOException {
        String text = Files.readString(path, StandardCharsets.US_ASCII);
        List<String> tokens = tokenize(text);
        if (tokens.size() < 4 || !tokens.get(0).equals("P3")) {
            throw new IllegalArgumentException("invalid P3 PPM");
        }
        int width = integer(tokens.get(1));
        int height = integer(tokens.get(2));
        int max = integer(tokens.get(3));
        if (width < 1 || width > 4096 || height < 1 || height > 4096 || max < 1 || max > 65535) {
            throw new IllegalArgumentException("PPM dimensions or max value out of range");
        }
        long count = (long) width * height * 3;
        if (count > 50_000_000 || tokens.size() != count + 4) {
            throw new IllegalArgumentException("wrong PPM sample count");
        }
        int[] samples = new int[(int) count];
        for (int i = 0; i < samples.length; i++) {
            int value = integer(tokens.get(i + 4));
            if (value < 0 || value > max) {
                throw new IllegalArgumentException("PPM sample out of range");
            }
            samples[i] = value;
        }
        return new PpmImage(width, height, max, samples);
    }

    private static List<String> tokenize(String text) {
        List<String> tokens = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        boolean comment = false;
        for (int i = 0; i < text.length(); i++) {
            char character = text.charAt(i);
            if (comment) {
                if (character == '\n' || character == '\r') {
                    comment = false;
                }
            } else if (character == '#') {
                if (!current.isEmpty()) {
                    tokens.add(current.toString());
                    current.setLength(0);
                }
                comment = true;
            } else if (Character.isWhitespace(character)) {
                if (!current.isEmpty()) {
                    tokens.add(current.toString());
                    current.setLength(0);
                }
            } else if (character > 127) {
                throw new IllegalArgumentException("PPM must be ASCII");
            } else {
                current.append(character);
            }
        }
        if (!current.isEmpty()) {
            tokens.add(current.toString());
        }
        return tokens;
    }

    private static int integer(String token) {
        try {
            if (token.isEmpty() || token.startsWith("+") || token.contains("-") && !token.startsWith("-")) {
                throw new NumberFormatException();
            }
            return Integer.parseInt(token);
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException("malformed PPM integer");
        }
    }
}
