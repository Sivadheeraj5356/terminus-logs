package nxq.play;
public final class Latch {
  public boolean armed;
  public void onWait(String room, java.util.Set<String> inv) {
    if ("buffer".equals(room) && inv.contains("patch")) armed = true;
  }
  public boolean trySeal(String target, java.util.Set<String> inv, java.util.Set<String> sealed) {
    if ("canary".equals(target) && armed && inv.contains("patch")) {
      sealed.add("canary");
      return true;
    }
    return false;
  }
}
