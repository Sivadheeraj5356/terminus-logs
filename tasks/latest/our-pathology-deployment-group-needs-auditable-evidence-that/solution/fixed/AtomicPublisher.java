package org.example.parity;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;

final class AtomicPublisher {
    private static final ObjectMapper MAPPER = JsonMapper.builder().build();

    private AtomicPublisher() {}

    static void write(Path output, ObjectNode report) throws IOException {
        Path parent = output.getParent();
        if (parent == null) {
            throw new IllegalArgumentException("output needs a parent directory");
        }
        rejectSymlinkComponents(output);
        Files.createDirectories(parent);
        rejectSymlinkComponents(output);
        byte[] bytes = (MAPPER.writeValueAsString(report) + "\n").getBytes(StandardCharsets.UTF_8);
        Path temporary = Files.createTempFile(parent, "." + output.getFileName() + ".", ".tmp");
        boolean moved = false;
        try {
            try (FileChannel channel = FileChannel.open(temporary, StandardOpenOption.WRITE,
                    StandardOpenOption.TRUNCATE_EXISTING)) {
                ByteBuffer buffer = ByteBuffer.wrap(bytes);
                while (buffer.hasRemaining()) {
                    channel.write(buffer);
                }
                channel.force(true);
            }
            Files.move(temporary, output, StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING);
            try (FileChannel directory = FileChannel.open(parent, StandardOpenOption.READ)) {
                directory.force(true);
            }
            moved = true;
        } finally {
            if (!moved) {
                Files.deleteIfExists(temporary);
            }
        }
    }

    private static void rejectSymlinkComponents(Path path) throws IOException {
        Path absolute = path.toAbsolutePath().normalize();
        Path current = absolute.getRoot();
        for (Path component : absolute) {
            current = current.resolve(component);
            if (Files.isSymbolicLink(current)) {
                throw new IllegalArgumentException("output path must not contain symlinks");
            }
            if (!Files.exists(current)) {
                break;
            }
        }
    }
}
