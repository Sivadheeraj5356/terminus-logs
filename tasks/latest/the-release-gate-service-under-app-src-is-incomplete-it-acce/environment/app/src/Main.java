package gate;

import com.sun.net.httpserver.HttpServer;

import java.net.InetSocketAddress;
import java.util.concurrent.Executors;

public final class Main {

    public static void main(String[] args) throws Exception {
        String host = System.getenv().getOrDefault("GATE_HOST", "127.0.0.1");
        int port = Integer.parseInt(System.getenv().getOrDefault("GATE_PORT", "8971"));
        String dbUrl = System.getenv().getOrDefault(
            "GATE_DB_URL",
            "jdbc:h2:file:/app/data/approvals;IFEXISTS=TRUE;ACCESS_MODE_DATA=r;AUTO_SERVER=FALSE");
        String standardPath = System.getenv().getOrDefault(
            "GATE_STANDARD", "/app/standard/cdss_v4.md");

        HttpApi api = new HttpApi(dbUrl, standardPath);

        HttpServer server = HttpServer.create(new InetSocketAddress(host, port), 32);
        server.createContext("/health", api::health);
        server.createContext("/gate/evaluate", api::evaluate);
        server.setExecutor(Executors.newFixedThreadPool(4));
        server.start();

        System.out.println("[gate] listening on " + host + ":" + port);

        // Graceful shutdown on SIGTERM.
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            server.stop(0);
        }));
    }
}
