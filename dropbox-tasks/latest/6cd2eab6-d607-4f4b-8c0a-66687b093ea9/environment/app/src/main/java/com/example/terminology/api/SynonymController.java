
package com.example.terminology.api;
import com.example.terminology.synonyms.SynonymService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Map;
@RestController
public class SynonymController {
  private final SynonymService service;
  public SynonymController(SynonymService service) { this.service = service; }
  @GetMapping("/v1/terms/{term}/synonyms")
  public ResponseEntity<Map<String, Object>> synonyms(@PathVariable String term) {
    List<Map<String, Object>> rows = service.lookup(term);
    if (rows.isEmpty()) {
      return ResponseEntity.status(404).body(Map.of(
        "error", Map.of("code", "term_not_found", "message", "No synonyms for term", "details", Map.of("term", term))
      ));
    }
    return ResponseEntity.ok(Map.of("term", term, "synonyms", rows));
  }
  @GetMapping("/health")
  public Map<String, String> health() { return Map.of("status", "ok"); }
}
