import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

// gosaw takes the path to a mill file as its single command-line argument, then reads one
// batch of rods per line from standard input and prints one line per batch it answers. The
// mill file gives the longest rod this bench will take. How a batch is read, whether the
// player to saw can force a win and which winning cut is reported are all handled by the
// Sawmill class this calls into.
public class Main {
    public static void main(String[] args) {
        if (args.length != 1) {
            System.exit(2);
        }

        Sawmill mill = null;
        try {
            mill = Sawmill.load(args[0]);
        } catch (Exception e) {
            mill = null;
        }
        if (mill == null) {
            System.exit(2);
        }

        StringBuilder input = new StringBuilder();
        try {
            byte[] all = System.in.readAllBytes();
            input.append(new String(all));
        } catch (IOException e) {
            // leave input empty
        }

        List<String> out = new ArrayList<>();
        for (String line : input.toString().split("\n", -1)) {
            String answer = mill.eval(line);
            if (answer != null) {
                out.add(answer);
            }
        }
        if (!out.isEmpty()) {
            System.out.print(String.join("\n", out) + "\n");
        }
    }
}
