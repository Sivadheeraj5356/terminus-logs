
package com.example.terminology.startup;
import com.example.terminology.assets.*;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;
import java.nio.file.Path;
@Component
public class StartupAssetGate implements ApplicationRunner {
  private final AssetLockLoader loader;
  private final AssetLockValidator validator;
  public StartupAssetGate(AssetLockLoader loader, AssetLockValidator validator) {
    this.loader = loader; this.validator = validator;
  }
  @Override
  public void run(ApplicationArguments args) throws Exception {
    try {
      AssetLock lock = loader.load(Path.of("/app/config/hf-assets.lock.json"));
      validator.validate(lock);
    } catch (Exception ex) {
      System.err.println("WARN asset lock: " + ex.getMessage());
    }
  }
}
