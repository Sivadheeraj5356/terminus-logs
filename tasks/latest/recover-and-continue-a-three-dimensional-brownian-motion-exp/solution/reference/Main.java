package org.terminus.calc;

import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import static org.terminus.calc.Model.*;

public final class Main {
    private Main() {}

    public static void main(String[] args) {
        try {
            if (args.length == 1 && "--help".equals(args[0])) {
                help();
                return;
            }
            if (args.length < 1) throw new Validation("missing mode");
            String mode = args[0];
            Map<String, String> flags = parseFlags(args);
            StateData state;
            Path statePath = required(flags, "--state");
            Path dbPath = required(flags, "--db");
            Path reportPath = required(flags, "--report");
            boolean writeState;
            switch (mode) {
                case "analyze" -> {
                    requireKeys(flags, Set.of("--spec", "--state", "--db", "--report"));
                    state = Recovery.snapshot(required(flags, "--spec"));
                    writeState = true;
                }
                case "resume" -> {
                    requireKeys(flags, Set.of("--spec", "--state", "--db", "--report"));
                    StateData previous = StateStore.read(statePath);
                    state = Recovery.snapshot(required(flags, "--spec"));
                    StateStore.requireExtension(previous, state);
                    writeState = true;
                }
                case "rebuild" -> {
                    requireKeys(flags, Set.of("--state", "--db", "--report"));
                    ensureDistinct(statePath, dbPath, reportPath);
                    state = StateStore.read(statePath);
                    writeState = false;
                }
                default -> throw new Validation("invalid mode");
            }
            Recovered recovered = Recovery.recover(state);
            AnalysisData analysis = Dynamics.compute(recovered);
            String report = ResultWriter.render(recovered, analysis);
            ResultWriter.publish(statePath, writeState, dbPath, reportPath, state, recovered, analysis, report);
            System.out.print(report);
        } catch (Validation e) {
            System.err.println(e.getMessage());
            System.exit(2);
        } catch (Insufficient e) {
            System.err.println(e.getMessage());
            System.exit(3);
        } catch (StateMismatch e) {
            System.err.println(e.getMessage());
            System.exit(4);
        } catch (Exception e) {
            System.err.println(e.getMessage());
            System.exit(5);
        }
    }

    private static Map<String, String> parseFlags(String[] args) throws Validation {
        if ((args.length - 1) % 2 != 0) throw new Validation("flags require values");
        Map<String, String> flags = new HashMap<>();
        Set<String> allowed = Set.of("--spec", "--state", "--db", "--report");
        for (int index = 1; index < args.length; index += 2) {
            String key = args[index];
            String value = args[index + 1];
            if (!allowed.contains(key) || value.isEmpty() || flags.put(key, value) != null) {
                throw new Validation("invalid arguments");
            }
        }
        return flags;
    }

    private static Path required(Map<String, String> flags, String name) throws Validation {
        String value = flags.get(name);
        if (value == null) throw new Validation("missing " + name);
        return Path.of(value);
    }

    private static void requireKeys(Map<String, String> flags, Set<String> keys) throws Validation {
        if (!flags.keySet().equals(keys)) throw new Validation("invalid flags for mode");
    }

    private static void ensureDistinct(Path... paths) throws Validation {
        Set<Path> seen = new java.util.HashSet<>();
        for (Path path : paths) {
            if (!seen.add(path.toAbsolutePath().normalize())) throw new Validation("state and output paths must be distinct");
        }
    }

    private static void help() {
        System.out.println("Usage:");
        System.out.println("  run.sh analyze --spec <definition> --state <checkpoint> --db <duckdb> --report <json>");
        System.out.println("  run.sh resume  --spec <definition> --state <checkpoint> --db <duckdb> --report <json>");
        System.out.println("  run.sh rebuild --state <checkpoint> --db <duckdb> --report <json>");
    }
}
