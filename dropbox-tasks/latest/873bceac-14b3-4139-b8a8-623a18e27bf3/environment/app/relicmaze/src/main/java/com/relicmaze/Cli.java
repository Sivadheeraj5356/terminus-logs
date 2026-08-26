package com.relicmaze;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Command-line driver used by the verifier. Reads a scenario JSON file of the
 * form {@code {"capsule": "<path>", "transcript": ["cmd", ...]}}, resolves it,
 * and prints the response to stdout in the canonical wire format:
 *
 * <pre>
 * &lt;narration&gt;
 * ---ACTIONS---
 * &lt;action-1&gt;
 * &lt;action-2&gt;
 * </pre>
 */
public final class Cli {
    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("usage: Cli <scenario.json>");
            System.exit(2);
        }
        String text = new String(Files.readAllBytes(Paths.get(args[0])));
        JSONObject scenario = new JSONObject(text);
        String capsule = scenario.getString("capsule");
        List<String> transcript = new ArrayList<>();
        JSONArray t = scenario.getJSONArray("transcript");
        for (int i = 0; i < t.length(); i++) {
            transcript.add(t.getString(i));
        }

        Response response = new Resolver().resolve(new Request(capsule, transcript));

        StringBuilder sb = new StringBuilder();
        sb.append(response.narration());
        sb.append("\n---ACTIONS---\n");
        sb.append(String.join("\n", response.actions()));
        sb.append("\n");
        System.out.print(sb);
    }
}
