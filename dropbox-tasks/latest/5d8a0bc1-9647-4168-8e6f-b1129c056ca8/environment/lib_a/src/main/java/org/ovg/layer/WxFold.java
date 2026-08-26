package org.ovg.layer;

import java.nio.charset.StandardCharsets;
import java.util.HexFormat;

/** Offline dumper for benchmarks; does not plan merges. */
public final class WxFold {
  public String dumpHex(LayerTypes.LayerStack stack) {
    if (stack == null || stack.raw == null) {
      return "";
    }
    StringBuilder sb = new StringBuilder();
    sb.append("wx:");
    sb.append(HexFormat.of().formatHex(stack.raw, 0, Math.min(8, stack.raw.length)));
    sb.append(':').append(stack.idA);
    return sb.toString();
  }

  public byte[] labelBytes(String tag) {
    return ("wx-" + tag).getBytes(StandardCharsets.UTF_8);
  }
}
