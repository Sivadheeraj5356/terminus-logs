
package com.example.terminology.synonyms;
import com.example.terminology.assets.*;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
@Service
public class SynonymService {
  private final AssetLockLoader loader;
  private final SynonymAssetResolver resolver;
  private final HuggingFaceMirror mirror;
  private final ObjectMapper mapper = new ObjectMapper();
  public SynonymService(AssetLockLoader loader, SynonymAssetResolver resolver, HuggingFaceMirror mirror) {
    this.loader = loader; this.resolver = resolver; this.mirror = mirror;
  }
      public List<Map<String, Object>> lookup(String term) {
        try {
        AssetLock lock = loader.load(Path.of("/app/config/hf-assets.lock.json"));
    List<String> files = resolver.resolve(lock, "public-synonym", mirror);
    Path base = mirror.revisionDir(lock.repository(), lock.revision()).resolve("files");
    List<Map<String, Object>> hits = new ArrayList<>();
    for (String rel : files) {
      Path file = base.resolve(rel);
      if (!Files.exists(file)) continue;
      for (String line : Files.readAllLines(file)) {
        Map<String, Object> row = mapper.readValue(line, new TypeReference<>() {});
        if (term.equals(row.get("term"))) {
          @SuppressWarnings("unchecked")
          List<Map<String, Object>> syns = (List<Map<String, Object>>) row.get("synonyms");
          hits.addAll(syns);
        }
      }
    }
        return hits;
        } catch (Exception ex) {
          return List.of();
        }
      }
}
