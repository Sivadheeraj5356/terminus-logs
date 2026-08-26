package com.relicmaze;

import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Batch driver used by the verifier. Resolves every scenario JSON in an input
 * directory and writes each response, in the canonical wire format, to
 * {@code <outDir>/<scenario-name>.txt}. Running the whole suite in one JVM keeps
 * verification fast.
 *
 * <pre>java com.relicmaze.BatchRunner &lt;scenarioDir&gt; &lt;outDir&gt;</pre>
 */
public final class BatchRunner {
    public static void main(String[] args) throws Exception {
        Path inDir = Paths.get(args[0]);
        Path outDir = Paths.get(args[1]);
        Files.createDirectories(outDir);

        List<Path> files = new ArrayList<>();
        try (DirectoryStream<Path> ds = Files.newDirectoryStream(inDir, "*.json")) {
            for (Path p : ds) {
                files.add(p);
            }
        }
        Collections.sort(files);

        Oracle resolver = new Resolver();
        for (Path f : files) {
            String file = f.getFileName().toString();
            String name = file.substring(0, file.length() - ".json".length());
            String out;
            try {
                JSONObject scenario = new JSONObject(new String(Files.readAllBytes(f)));
                String capsule = scenario.getString("capsule");
                List<String> transcript = new ArrayList<>();
                JSONArray t = scenario.getJSONArray("transcript");
                for (int i = 0; i < t.length(); i++) {
                    transcript.add(t.getString(i));
                }
                Response r = resolver.resolve(new Request(capsule, transcript));
                out = r.narration() + "\n---ACTIONS---\n" + String.join("\n", r.actions()) + "\n";
            } catch (Exception e) {
                out = "<<resolver error>> " + e + "\n";
            }
            Files.write(outDir.resolve(name + ".txt"), out.getBytes());
        }
    }
}
