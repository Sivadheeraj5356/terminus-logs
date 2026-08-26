package com.example.terminology.assets;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record AssetLock(
    @JsonProperty("lock_schema_version") String lockSchemaVersion,
    @JsonProperty("repository") String repository,
    @JsonProperty("revision") String revision,
    @JsonProperty("source_metadata_digest") String sourceMetadataDigest,
    @JsonProperty("transcript_digest") String transcriptDigest,
    @JsonProperty("gradle_lock_digest") String gradleLockDigest,
    @JsonProperty("routes") List<RouteAssets> routes
) {
  public record RouteAssets(
      @JsonProperty("route_id") String routeId,
      @JsonProperty("files") List<FileAsset> files
  ) {}

  public record FileAsset(
      @JsonProperty("path") String path,
      @JsonProperty("sha256") String sha256,
      @JsonProperty("bytes") long bytes
  ) {}
}
