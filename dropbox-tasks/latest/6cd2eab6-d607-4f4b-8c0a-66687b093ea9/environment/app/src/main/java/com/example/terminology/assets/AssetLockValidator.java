
package com.example.terminology.assets;
import org.springframework.stereotype.Component;
@Component
public class AssetLockValidator {
  public void validate(AssetLock lock) {
    if (lock.revision() == null || lock.revision().isBlank()) {
      throw new IllegalStateException("missing revision");
    }
  }
}
