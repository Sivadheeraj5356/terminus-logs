package org.example.parity;

import java.nio.file.Path;

record ManifestEntry(String id, String image, String sha256, String group, Path path) {}
