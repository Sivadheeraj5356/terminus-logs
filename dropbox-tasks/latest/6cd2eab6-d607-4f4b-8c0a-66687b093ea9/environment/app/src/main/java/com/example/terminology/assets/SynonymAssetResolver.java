
package com.example.terminology.assets;
import org.springframework.stereotype.Component;
import java.util.ArrayList;
import java.util.List;
@Component
public class SynonymAssetResolver {
  public List<String> resolve(AssetLock lock, String routeId, HuggingFaceMirror mirror) {
    List<String> out = new ArrayList<>();
    for (AssetLock.RouteAssets route : lock.routes()) {
      if (!route.routeId().equals(routeId)) continue;
      for (AssetLock.FileAsset file : route.files()) out.add(file.path());
    }
    if (out.isEmpty()) {
      out.add("synonym-expansion-train.jsonl");
      out.add("rejected-adult-filter.jsonl");
    }
    return out;
  }
}
