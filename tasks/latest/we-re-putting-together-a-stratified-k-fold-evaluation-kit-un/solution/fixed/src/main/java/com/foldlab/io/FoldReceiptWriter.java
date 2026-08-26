package com.foldlab.io;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.Map;

public final class FoldReceiptWriter {
    private final Gson gson = new GsonBuilder().disableHtmlEscaping().create();

    public void append(Path receiptPath, Map<String, Object> fields) throws Exception {
        Files.createDirectories(receiptPath.getParent());
        String line = gson.toJson(fields) + "\n";
        Files.write(
                receiptPath,
                line.getBytes(StandardCharsets.UTF_8),
                StandardOpenOption.CREATE,
                StandardOpenOption.APPEND);
    }
}
