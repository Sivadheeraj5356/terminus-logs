package com.relicmaze;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Reads an inert OCI-style capsule image config. Only the raw pieces are
 * surfaced here: the {@code config.Labels} map, the {@code config.Env} list,
 * and the {@code created_by} string of every {@code history} entry, in order.
 * Interpreting those into game directives is the resolver's job.
 */
public final class CapsuleSpec {
    private final Map<String, String> labels;
    private final List<String> env;
    private final List<String> history;

    private CapsuleSpec(Map<String, String> labels, List<String> env, List<String> history) {
        this.labels = labels;
        this.env = env;
        this.history = history;
    }

    public Map<String, String> labels() {
        return labels;
    }

    public List<String> env() {
        return env;
    }

    /** The {@code created_by} field of each history entry, top to bottom. */
    public List<String> history() {
        return history;
    }

    public static CapsuleSpec load(String path) throws Exception {
        String text = new String(Files.readAllBytes(Paths.get(path)));
        JSONObject root = new JSONObject(text);

        Map<String, String> labels = new LinkedHashMap<>();
        List<String> env = new ArrayList<>();
        if (root.has("config")) {
            JSONObject config = root.getJSONObject("config");
            if (config.has("Labels") && !config.isNull("Labels")) {
                JSONObject l = config.getJSONObject("Labels");
                for (String key : l.keySet()) {
                    labels.put(key, l.getString(key));
                }
            }
            if (config.has("Env") && !config.isNull("Env")) {
                JSONArray e = config.getJSONArray("Env");
                for (int i = 0; i < e.length(); i++) {
                    env.add(e.getString(i));
                }
            }
        }

        List<String> history = new ArrayList<>();
        if (root.has("history") && !root.isNull("history")) {
            JSONArray h = root.getJSONArray("history");
            for (int i = 0; i < h.length(); i++) {
                JSONObject entry = h.getJSONObject(i);
                if (entry.has("created_by") && !entry.isNull("created_by")) {
                    history.add(entry.getString("created_by"));
                }
            }
        }

        return new CapsuleSpec(labels, env, history);
    }
}
