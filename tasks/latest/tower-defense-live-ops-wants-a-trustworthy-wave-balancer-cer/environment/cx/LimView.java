package cx;

public final class LimView {
    public final int maxCost;
    public final double minLeft;
    public final double maxAmp;
    public final byte[] salt;

    public LimView(int maxCost, double minLeft, double maxAmp, byte[] salt) {
        this.maxCost = maxCost;
        this.minLeft = minLeft;
        this.maxAmp = maxAmp;
        this.salt = salt;
    }
}
