package com.example.terminology.startup;

import com.example.terminology.assets.AssetLock;
import com.example.terminology.assets.AssetLockLoader;
import com.example.terminology.assets.AssetLockValidator;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;
import java.nio.file.Path;

@Component
public class StartupAssetGate implements ApplicationRunner {
  private final AssetLockLoader loader;
  private final AssetLockValidator validator;

  public StartupAssetGate(AssetLockLoader loader, AssetLockValidator validator) {
    this.loader = loader;
    this.validator = validator;
  }

  @Override
  public void run(ApplicationArguments args) throws Exception {
    Path lockPath = Path.of(System.getenv().getOrDefault("HF_ASSET_LOCK", "/app/config/hf-assets.lock.json"));
    AssetLock lock = loader.load(lockPath);
    validator.validate(lock);
  }
}
