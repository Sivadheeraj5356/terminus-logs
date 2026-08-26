package com.example.terminology.assets;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import java.nio.file.Path;

@Component
public class HuggingFaceMirror {
  @Value("${hf.mirror-root:/data/hf-mirror}")
  private String mirrorRoot;

  public Path revisionDir(String repo, String revision) {
    return Path.of(mirrorRoot, repo, "fineweb-edu-score-2", "revisions", revision);
  }
}
