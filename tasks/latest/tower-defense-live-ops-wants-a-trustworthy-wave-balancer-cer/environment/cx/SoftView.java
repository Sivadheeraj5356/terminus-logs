package cx;

public final class SoftView {
    public final double softFloor;
    public final double egressCap;
    public final int digits;

    public SoftView(double softFloor, double egressCap, int digits) {
        this.softFloor = softFloor;
        this.egressCap = egressCap;
        this.digits = digits;
    }
}
