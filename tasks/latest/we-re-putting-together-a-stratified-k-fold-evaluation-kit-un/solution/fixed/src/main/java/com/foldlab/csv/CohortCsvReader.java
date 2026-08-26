package com.foldlab.csv;

import com.foldlab.model.FoldRow;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class CohortCsvReader {
    public List<FoldRow> read(Path csvPath, String labelColumn) throws IOException {
        List<String> lines = Files.readAllLines(csvPath, StandardCharsets.UTF_8);
        if (lines.isEmpty()) {
            return List.of();
        }
        String[] header = lines.get(0).split(",", -1);
        Map<String, Integer> index = new HashMap<>();
        for (int i = 0; i < header.length; i++) {
            index.put(header[i].trim(), i);
        }
        if (!index.containsKey("id") || !index.containsKey(labelColumn)) {
            throw new IOException("missing required columns");
        }
        int idIdx = index.get("id");
        int labelIdx = index.get(labelColumn);
        List<FoldRow> rows = new ArrayList<>();
        for (int lineNo = 1; lineNo < lines.size(); lineNo++) {
            String line = lines.get(lineNo);
            if (line.isBlank()) {
                continue;
            }
            String[] parts = line.split(",", -1);
            rows.add(new FoldRow(parts[idIdx].trim(), parts[labelIdx].trim()));
        }
        return rows;
    }
}
