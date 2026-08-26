package org.mrgo.spectra;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * spectra-svc: FFT band-power spectra for Meridian Ridge telemetry frames.
 * Endpoints: /health, /channels, /bandpower?channel=..&from=..&to=..
 */
public final class SpectraServer {

    private static final int PORT = 8747;
    private static final ObjectMapper MAPPER = new ObjectMapper();

    public static void main(String[] args) throws Exception {
        QueryService queries = new QueryService();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", PORT), 0);

        server.createContext("/health", ex -> {
            ObjectNode body = MAPPER.createObjectNode();
            body.put("status", "ok");
            respond(ex, 200, body);
        });

        server.createContext("/channels", ex -> {
            try {
                List<String> names = queries.listChannels();
                ObjectNode body = MAPPER.createObjectNode();
                ArrayNode arr = body.putArray("channels");
                names.forEach(arr::add);
                respond(ex, 200, body);
            } catch (Exception e) {
                error(ex, 500, e.getMessage());
            }
        });

        server.createContext("/bandpower", ex -> {
            try {
                Map<String, String> q = queryParams(ex);
                String channel = q.get("channel");
                String from = q.get("from");
                String to = q.get("to");
                if (channel == null || from == null || to == null) {
                    error(ex, 400, "channel, from and to are required");
                    return;
                }
                OffsetDateTime.parse(from);
                OffsetDateTime.parse(to);
                List<double[]> frames = queries.fetchFrames(channel, from, to);
                if (frames.isEmpty()) {
                    error(ex, 404, "no frames for channel in window");
                    return;
                }
                double[][] spectra = new double[frames.size()][];
                for (int i = 0; i < frames.size(); i++) {
                    spectra[i] = Welch.powerSpectralDensity(frames.get(i), QueryService.SAMPLE_RATE_HZ);
                }
                double[] mean = new double[spectra[0].length];
                for (double[] psd : spectra) {
                    for (int k = 0; k < mean.length; k++) {
                        mean[k] += psd[k] / spectra.length;
                    }
                }
                ObjectNode body = MAPPER.createObjectNode();
                body.put("channel", channel);
                body.put("frames", frames.size());
                body.put("revision", "C");
                ArrayNode arr = body.putArray("bands");
                for (Bands.Band band : Bands.TABLE) {
                    ObjectNode row = arr.addObject();
                    row.put("band", band.name());
                    row.put("lo_hz", band.loHz());
                    row.put("hi_hz", band.hiHz());
                    row.put("power", Bands.bandPower(mean, band, QueryService.SAMPLE_RATE_HZ, Welch.SEGMENT_LENGTH));
                }
                respond(ex, 200, body);
            } catch (Exception e) {
                error(ex, 500, e.getMessage());
            }
        });

        server.start();
        System.out.println("spectra-svc listening on 127.0.0.1:" + PORT);
    }

    private static Map<String, String> queryParams(HttpExchange ex) {
        Map<String, String> out = new HashMap<>();
        String raw = ex.getRequestURI().getRawQuery();
        if (raw == null) {
            return out;
        }
        for (String pair : raw.split("&")) {
            int eq = pair.indexOf('=');
            if (eq > 0) {
                String key = URLDecoder.decode(pair.substring(0, eq), StandardCharsets.UTF_8);
                String val = URLDecoder.decode(pair.substring(eq + 1), StandardCharsets.UTF_8);
                out.put(key, val);
            }
        }
        return out;
    }

    private static void respond(HttpExchange ex, int code, ObjectNode body) throws IOException {
        byte[] payload = MAPPER.writeValueAsBytes(body);
        ex.getResponseHeaders().set("Content-Type", "application/json");
        ex.sendResponseHeaders(code, payload.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(payload);
        }
    }

    private static void error(HttpExchange ex, int code, String message) throws IOException {
        ObjectNode body = MAPPER.createObjectNode();
        body.put("error", message == null ? "internal error" : message);
        respond(ex, code, body);
    }
}
