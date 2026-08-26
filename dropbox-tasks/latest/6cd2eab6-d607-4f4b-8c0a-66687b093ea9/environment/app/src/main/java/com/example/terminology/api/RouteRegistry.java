
package com.example.terminology.api;
import org.springframework.stereotype.Component;
import java.util.Map;
@Component
public class RouteRegistry {
  public String routeForPath(String path) {
    if (path.startsWith("/v1/terms/")) return "public-synonym";
    return "unknown";
  }
  public String apiPathForRoute(String routeId) {
    return Map.of("public-synonym", "/v1/terms/{term}/synonyms").getOrDefault(routeId, "/unknown");
  }
}
