package org.ovg.daemon;

import java.nio.file.Path;

/** Matrix phase driver entry. */
public final class Main {
  public static void main(String[] args) throws Exception {
    // Daemon entry is invoked via drive_grid.sh; keep a minimal main for classpath checks.
    Path root = Path.of("/app/environment");
    String cp = System.getProperty("ovg.cp", "");
    if (cp.isEmpty()) {
      System.err.println("ovg.cp required");
      System.exit(2);
    }
    Run run = new Run(root, cp);
    System.out.println("daemon_ready:" + run.getClass().getSimpleName());
  }
}
