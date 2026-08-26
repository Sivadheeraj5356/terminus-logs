static char stash_id[32];

void stash_bind(const char *id) {
    int i = 0;
    while (id[i] && i < 31) {
        stash_id[i] = id[i];
        i++;
    }
    stash_id[i] = '\0';
}
