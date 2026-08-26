package n3.k2;

import java.util.ArrayList;
import java.util.List;

/** Shared row carriers for lane folding. */
public final class TypesA {
  private TypesA() {}

  public static final class Connection {
    public final List<IssueRow> issue;
    public final List<RevRow> revoke;

    public Connection(List<IssueRow> issue, List<RevRow> revoke) {
      this.issue = issue;
      this.revoke = revoke;
    }
  }

  public static final class IssueRow {
    public final String pid;
    public final int gen;
    public final int ts;
    public final String scp;
    public final String role;

    public IssueRow(String pid, int gen, int ts, String scp, String role) {
      this.pid = pid;
      this.gen = gen;
      this.ts = ts;
      this.scp = scp;
      this.role = role;
    }
  }

  public static final class RevRow {
    public final String pid;
    public final int gen;
    public final int revoked;

    public RevRow(String pid, int gen, int revoked) {
      this.pid = pid;
      this.gen = gen;
      this.revoked = revoked;
    }
  }

  public static final class GenKey {
    public final int gen;
    public final String label;

    public GenKey(int gen, String label) {
      this.gen = gen;
      this.label = label;
    }
  }

  public static final class EpochCand {
    public final String pid;
    public final int gen;
    public final String scp;
    public final String role;
    public final long tag;

    public EpochCand(String pid, int gen, String scp, String role, long tag) {
      this.pid = pid;
      this.gen = gen;
      this.scp = scp;
      this.role = role;
      this.tag = tag;
    }
  }
}
