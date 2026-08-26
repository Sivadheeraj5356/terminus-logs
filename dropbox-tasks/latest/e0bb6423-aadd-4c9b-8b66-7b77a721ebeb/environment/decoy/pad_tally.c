int pad_tally(int *buf, int n, int fill) {
    for (int i = 0; i < n; i++) buf[i] = fill;
    return n;
}
