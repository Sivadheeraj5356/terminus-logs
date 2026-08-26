import java.io.IOException;

public final class Main {

    public static void main(String[] args) throws IOException {
        if (args.length < 1) {
            System.err.println("usage: solver <bundle_dir>");
            System.exit(2);
        }
        System.out.println("{\"n_events\":0,\"predictions\":[],\"checkpoints\":[]}");
    }

    private Main() {
    }
}
