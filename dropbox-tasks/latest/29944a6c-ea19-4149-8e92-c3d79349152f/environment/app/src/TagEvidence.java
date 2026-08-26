package gate;

import java.nio.file.Path;
import java.time.Instant;
import java.util.List;

/** Signature and approval evidence for a release tag. */
public final class TagEvidence {

    private TagEvidence() { }

    /** Collect signature evidence for {@code tag} inside {@code repoRoot}. */
    public static Result forTag(Path repoRoot, String tag) {
        // TODO: implement per Chapter 17.
        return new Result(false, null, null);
    }

    /** Decide whether the extracted evidence approves. Return null on approve. */
    public static PolicyEngine.Reason approve(Result evidence,
                                              List<Db.ApprovedKey> approvedKeys) {
        // TODO: implement per Chapter 17.
        return new PolicyEngine.Reason("§17.1", "CDSS-KEY-UNIMPL", "");
    }

    public record Result(boolean signatureValid, String fingerprint,
                          Instant tagCreatedAt) { }
}
