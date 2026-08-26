package sim;

public final class Main {
    public static void main(String[] args) {
        if (args.length < 4) {
            System.out.println("{\"ran\":false,\"maxView\":0,\"acked\":[],\"committed\":[],\"violation\":\"bad_args\"}");
            System.exit(2);
            return;
        }
        String mode = args[0];
        long seed = Long.parseLong(args[1]);
        int n = Integer.parseInt(args[2]);
        String impl = args[3];
        Engine engine = new Engine(n, impl);
        Verdict v;
        switch (mode) {
            case "control":
                v = engine.runControl(seed);
                break;
            case "clean":
                v = engine.runClean(seed, false);
                break;
            case "clean_reorder":
                v = engine.runClean(seed, true);
                break;
            case "failover":
                v = engine.runFailover(seed, false, false);
                break;
            case "failover_reorder":
                v = engine.runFailover(seed, true, false);
                break;
            case "failover_b2b":
                v = engine.runFailover(seed, false, true);
                break;
            case "minority":
                v = engine.runMinority(seed);
                break;
            case "stale_ack":
                v = engine.runStaleAck(seed, false);
                break;
            case "stale_ack_wide":
                v = engine.runStaleAck(seed, false);
                break;
            case "stale_ack_reorder":
                v = engine.runStaleAck(seed, true);
                break;
            case "forge":
                v = engine.runForge(seed, false);
                break;
            case "forge_reorder":
                v = engine.runForge(seed, true);
                break;
            case "forge_wide":
                v = engine.runForge(seed, false);
                break;
            case "forge_small":
                v = engine.runForge(seed, false);
                break;
            case "replay":
                v = engine.runReplay(seed, false, false);
                break;
            case "replay_reorder":
                v = engine.runReplay(seed, true, false);
                break;
            case "replay_b2b":
                v = engine.runReplay(seed, false, true);
                break;
            case "restart":
                v = engine.runRestart(seed, false, false, "");
                break;
            case "restart_wide":
                v = engine.runRestart(seed, false, false, "");
                break;
            case "restart_small":
                v = engine.runRestart(seed, false, false, "");
                break;
            case "restart_reorder":
                v = engine.runRestart(seed, true, false, "");
                break;
            case "restart_b2b":
                v = engine.runRestart(seed, false, true, "");
                break;
            case "restart_forge":
                v = engine.runRestart(seed, false, false, "forge");
                break;
            case "restart_replay":
                v = engine.runRestart(seed, false, false, "replay");
                break;
            case "recover_replay":
                v = engine.runRestart(seed, false, false, "recover_replay");
                break;
            default:
                v = new Verdict();
                v.violation = "unknown_mode";
                break;
        }
        System.out.println(v.toJson());
    }
}
