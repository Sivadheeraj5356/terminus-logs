package org.ovg.emit;

import java.util.LinkedHashMap;
import java.util.Map;

/** Accumulates proof-log instance rows. */
public final class ProofSink {
  private final Map<String, Map<String, Object>> rows = new LinkedHashMap<>();
  private byte[] plan = new byte[0];
  private String armId = "";
  private String pathKind = "";

  public void setPlan(byte[] planBytes) {
    this.plan = planBytes == null ? new byte[0] : planBytes.clone();
  }

  public byte[] getPlan() {
    return plan.clone();
  }

  public void setMeta(String armId, String pathKind) {
    this.armId = armId == null ? "" : armId;
    this.pathKind = pathKind == null ? "" : pathKind;
  }

  public String getArmId() {
    return armId;
  }

  public String getPathKind() {
    return pathKind;
  }

  public void put(String key, Map<String, Object> row) {
    rows.put(key, new LinkedHashMap<>(row));
  }

  public Map<String, Map<String, Object>> snapshot() {
    Map<String, Map<String, Object>> out = new LinkedHashMap<>();
    for (Map.Entry<String, Map<String, Object>> e : rows.entrySet()) {
      out.put(e.getKey(), new LinkedHashMap<>(e.getValue()));
    }
    return out;
  }
}
