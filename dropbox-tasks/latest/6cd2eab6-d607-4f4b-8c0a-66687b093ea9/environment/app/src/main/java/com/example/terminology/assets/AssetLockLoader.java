
package com.example.terminology.assets;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;
import java.nio.file.Path;
@Component
public class AssetLockLoader {
  private final ObjectMapper mapper = new ObjectMapper();
  public AssetLock load(Path path) throws Exception {
    return mapper.readValue(path.toFile(), AssetLock.class);
  }
}
