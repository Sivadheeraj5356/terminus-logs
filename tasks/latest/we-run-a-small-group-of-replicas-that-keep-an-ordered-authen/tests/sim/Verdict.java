package sim;

import java.util.List;

public final class Verdict {
    public boolean ran;
    public int maxView;
    public List<Integer> acked;
    public List<Integer> committed;
    public String violation;

    public String toJson() {
        StringBuilder sb = new StringBuilder();
        sb.append("{\"ran\":").append(ran);
        sb.append(",\"maxView\":").append(maxView);
        sb.append(",\"acked\":").append(list(acked));
        sb.append(",\"committed\":").append(list(committed));
        sb.append(",\"violation\":");
        if (violation == null) {
            sb.append("null");
        } else {
            sb.append('"').append(violation).append('"');
        }
        sb.append('}');
        return sb.toString();
    }

    private static String list(List<Integer> xs) {
        StringBuilder sb = new StringBuilder("[");
        if (xs != null) {
            for (int i = 0; i < xs.size(); i++) {
                if (i > 0) {
                    sb.append(',');
                }
                sb.append(xs.get(i));
            }
        }
        sb.append(']');
        return sb.toString();
    }
}
