package t5.r4;

import java.util.List;

/** No-op seal stubs for smoke packs; never feeds x7. */
public final class ZipStub {
  private ZipStub() {}

  public static TypesC.SealRecord StubSeal(List<TypesC.StageRow> stages) {
    return new TypesC.SealRecord("0".repeat(64), 0, 0, new byte[0]);
  }
}
