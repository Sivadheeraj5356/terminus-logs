package gate;

import java.nio.file.Path;

/** Verifies the repository hooks configuration and pre-push marker. */
public final class HookCheck {

    private HookCheck() { }

    public static Result check(Path repoRoot, String standardSha256) {
        // TODO: implement per Chapter 22.
        return new Result(false);
    }

    public record Result(boolean ok) { }
}
