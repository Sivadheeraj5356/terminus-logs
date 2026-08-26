#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#define MAX_SAMPLES 64
#define MAX_PANELS 24
#define MAX_REQ 32
#define MAX_FORBID 128
#define MAX_LINK 128
#define MAX_BLOCKS 96
#define MAX_SETUP 128
#define TEXT 128
#define LINE 1024

typedef struct {
    char id[TEXT], family[TEXT], cohort[TEXT];
    int risk, reagent_a, reagent_b, mandatory;
} Sample;

typedef struct {
    char id[TEXT], families[TEXT], cls[TEXT];
    int cap_a, cap_b, slot_cap;
} Panel;

typedef struct {
    int members[2];
    int count;
    int required;
    int risk;
    int options;
} Block;

static Sample samples[MAX_SAMPLES];
static Panel panels[MAX_PANELS];
static Block blocks[MAX_BLOCKS];
static int sample_count, panel_count, block_count;
static char required_families[MAX_REQ][TEXT], sentinel_families[MAX_REQ][TEXT];
static int required_count, sentinel_count, min_sentinel_panels, risk_floor, risk_target = 1;
static int cohort_separation;
static char forbid_l[MAX_FORBID][TEXT], forbid_r[MAX_FORBID][TEXT];
static int forbid_count;
static char link_l[MAX_LINK][TEXT], link_r[MAX_LINK][TEXT];
static int link_count, linked_pair_floor;
static char setup_from[MAX_SETUP][TEXT], setup_to[MAX_SETUP][TEXT];
static int setup_value[MAX_SETUP], setup_count;
static char lane_target_family[MAX_PANELS][TEXT];
static int lane_count, min_lane_panels, max_lane_panels = 999, lane_setup_cap = 999999, total_setup_cap = 999999;
static int setup_target = 1;
static int order[MAX_BLOCKS], assign_now[MAX_SAMPLES], best_assign[MAX_SAMPLES];
static int active_panels[MAX_PANELS], active_count;
static int sched_lane[MAX_PANELS][MAX_PANELS], sched_len[MAX_PANELS], best_sched_lane[MAX_PANELS][MAX_PANELS], best_sched_len[MAX_PANELS];
static int sched_used[MAX_PANELS], best_setup_total = 999999;
static int used_a[MAX_PANELS], used_b[MAX_PANELS], used_slots[MAX_PANELS];
static int assigned_now, risk_now;
static double best_strict = -1.0, best_public = -1.0;
static int found_good_solution = 0;

static void trim(char *s) {
    size_t n = strlen(s);
    while (n && (s[n - 1] == '\n' || s[n - 1] == '\r')) {
        s[--n] = 0;
    }
}

static int contains_token(const char *list, const char *token) {
    char buf[TEXT * 4];
    char needle[TEXT + 4];
    snprintf(buf, sizeof(buf), "|%s|", list);
    snprintf(needle, sizeof(needle), "|%s|", token);
    return strstr(buf, needle) != NULL;
}

static int in_list(char arr[MAX_REQ][TEXT], int count, const char *value) {
    for (int i = 0; i < count; i++) {
        if (strcmp(arr[i], value) == 0) return 1;
    }
    return 0;
}

static void split_to_array(const char *src, char out[MAX_REQ][TEXT], int *count) {
    char buf[TEXT * 4];
    snprintf(buf, sizeof(buf), "%s", src);
    char *tok = strtok(buf, "|");
    while (tok && *count < MAX_REQ) {
        snprintf(out[*count], TEXT, "%s", tok);
        (*count)++;
        tok = strtok(NULL, "|");
    }
}

static void load_config(const char *path) {
    FILE *fh = fopen(path, "r");
    if (!fh) exit(2);
    char line[LINE];
    while (fgets(line, sizeof(line), fh)) {
        trim(line);
        if (!line[0]) continue;
        char *eq = strchr(line, '=');
        if (!eq) continue;
        *eq = '\0';
        char *key = line;
        char *val = eq + 1;
        if (strcmp(key, "families") == 0) {
            split_to_array(val, required_families, &required_count);
        } else if (strcmp(key, "sentinel_families") == 0) {
            split_to_array(val, sentinel_families, &sentinel_count);
        } else if (strcmp(key, "risk_floor") == 0) {
            risk_floor = atoi(val);
        } else if (strcmp(key, "risk_target") == 0) {
            risk_target = atoi(val);
        } else if (strcmp(key, "min_sentinel_panels") == 0) {
            min_sentinel_panels = atoi(val);
        } else if (strcmp(key, "cohort_separation") == 0) {
            cohort_separation = atoi(val);
        } else if (strcmp(key, "forbidden_pairs") == 0) {
            char buf[LINE];
            snprintf(buf, sizeof(buf), "%s", val);
            char *pair = strtok(buf, "|");
            while (pair && forbid_count < MAX_FORBID) {
                char *sep = strchr(pair, ':');
                if (sep) {
                    *sep = '\0';
                    snprintf(forbid_l[forbid_count], TEXT, "%s", pair);
                    snprintf(forbid_r[forbid_count], TEXT, "%s", sep + 1);
                    forbid_count++;
                }
                pair = strtok(NULL, "|");
            }
        } else if (strcmp(key, "linked_pairs") == 0) {
            char buf[LINE];
            snprintf(buf, sizeof(buf), "%s", val);
            char *pair = strtok(buf, "|");
            while (pair && link_count < MAX_LINK) {
                char *sep = strchr(pair, ':');
                if (sep) {
                    *sep = '\0';
                    snprintf(link_l[link_count], TEXT, "%s", pair);
                    snprintf(link_r[link_count], TEXT, "%s", sep + 1);
                    link_count++;
                }
                pair = strtok(NULL, "|");
            }
        } else if (strcmp(key, "linked_pair_floor") == 0) {
            linked_pair_floor = atoi(val);
        } else if (strcmp(key, "lane_count") == 0) {
            lane_count = atoi(val);
        } else if (strcmp(key, "min_lane_panels") == 0) {
            min_lane_panels = atoi(val);
        } else if (strcmp(key, "max_lane_panels") == 0) {
            max_lane_panels = atoi(val);
        } else if (strcmp(key, "lane_setup_cap") == 0) {
            lane_setup_cap = atoi(val);
        } else if (strcmp(key, "total_setup_cap") == 0) {
            total_setup_cap = atoi(val);
        } else if (strcmp(key, "setup_target") == 0) {
            setup_target = atoi(val);
        } else if (strcmp(key, "lane_targets") == 0) {
            char buf[LINE];
            snprintf(buf, sizeof(buf), "%s", val);
            char *item = strtok(buf, "|");
            while (item) {
                char *sep = strchr(item, ':');
                if (sep) {
                    *sep = '\0';
                    int lane = atoi(item + 1);
                    if (lane >= 1 && lane < MAX_PANELS) {
                        snprintf(lane_target_family[lane - 1], TEXT, "%s", sep + 1);
                    }
                }
                item = strtok(NULL, "|");
            }
        } else if (strcmp(key, "setup_costs") == 0) {
            char buf[LINE * 2];
            snprintf(buf, sizeof(buf), "%s", val);
            char *item = strtok(buf, "|");
            while (item && setup_count < MAX_SETUP) {
                char *a = item;
                char *b = strchr(a, ':');
                if (b) {
                    *b++ = '\0';
                    char *c = strchr(b, ':');
                    if (c) {
                        *c++ = '\0';
                        snprintf(setup_from[setup_count], TEXT, "%s", a);
                        snprintf(setup_to[setup_count], TEXT, "%s", b);
                        setup_value[setup_count] = atoi(c);
                        setup_count++;
                    }
                }
                item = strtok(NULL, "|");
            }
        }
    }
    fclose(fh);
    if (risk_target <= 0) risk_target = risk_floor > 0 ? risk_floor : 1;
    if (lane_count <= 0) lane_count = 1;
    if (setup_target <= 0) setup_target = total_setup_cap;
}

static void load_samples(const char *path) {
    FILE *fh = fopen(path, "r");
    if (!fh) exit(2);
    char line[LINE];
    if (!fgets(line, sizeof(line), fh)) {
        fclose(fh);
        return;
    }
    while (fgets(line, sizeof(line), fh)) {
        trim(line);
        if (!line[0]) continue;
        Sample *s = &samples[sample_count];
        char *tok = strtok(line, "\t");
        if (!tok) continue;
        snprintf(s->id, TEXT, "%s", tok);
        tok = strtok(NULL, "\t");
        if (!tok) continue;
        snprintf(s->family, TEXT, "%s", tok);
        tok = strtok(NULL, "\t");
        if (!tok) continue;
        s->risk = atoi(tok);
        tok = strtok(NULL, "\t");
        if (!tok) continue;
        s->reagent_a = atoi(tok);
        tok = strtok(NULL, "\t");
        if (!tok) continue;
        s->reagent_b = atoi(tok);
        tok = strtok(NULL, "\t");
        if (!tok) continue;
        s->mandatory = atoi(tok);
        tok = strtok(NULL, "\t");
        if (!tok) continue;
        snprintf(s->cohort, TEXT, "%s", tok);
        sample_count++;
    }
    fclose(fh);
}

static void load_panels(const char *path) {
    FILE *fh = fopen(path, "r");
    if (!fh) exit(2);
    char line[LINE];
    if (!fgets(line, sizeof(line), fh)) {
        fclose(fh);
        return;
    }
    while (fgets(line, sizeof(line), fh)) {
        trim(line);
        if (!line[0]) continue;
        Panel *p = &panels[panel_count];
        char *tok = strtok(line, "\t");
        if (!tok) continue;
        snprintf(p->id, TEXT, "%s", tok);
        tok = strtok(NULL, "\t");
        if (!tok) continue;
        snprintf(p->families, TEXT, "%s", tok);
        tok = strtok(NULL, "\t");
        if (!tok) continue;
        p->cap_a = atoi(tok);
        tok = strtok(NULL, "\t");
        if (!tok) continue;
        p->cap_b = atoi(tok);
        tok = strtok(NULL, "\t");
        if (!tok) continue;
        p->slot_cap = atoi(tok);
        tok = strtok(NULL, "\t");
        if (!tok) continue;
        snprintf(p->cls, TEXT, "%s", tok);
        panel_count++;
    }
    fclose(fh);
}

static int sample_index(const char *id) {
    for (int i = 0; i < sample_count; i++) {
        if (strcmp(samples[i].id, id) == 0) return i;
    }
    return -1;
}

static int eligible(int sample_idx, int panel_idx) {
    return contains_token(panels[panel_idx].families, samples[sample_idx].family);
}

static int block_option_count(Block *b) {
    int count = b->required ? 0 : 1;
    for (int p = 0; p < panel_count; p++) {
        int ok = 1;
        for (int m = 0; m < b->count; m++) {
            if (!eligible(b->members[m], p)) ok = 0;
        }
        count += ok;
    }
    return count;
}

static void build_blocks(void) {
    int consumed[MAX_SAMPLES] = {0};
    for (int f = 0; f < link_count; f++) {
        int left = sample_index(link_l[f]);
        int right = sample_index(link_r[f]);
        if (left < 0 || right < 0 || left == right) continue;
        Block *b = &blocks[block_count++];
        b->members[0] = left;
        b->members[1] = right;
        b->count = 2;
        b->required = samples[left].mandatory || samples[right].mandatory;
        b->risk = samples[left].risk + samples[right].risk;
        consumed[left] = consumed[right] = 1;
    }
    for (int i = 0; i < sample_count; i++) {
        if (consumed[i]) continue;
        Block *b = &blocks[block_count++];
        b->members[0] = i;
        b->members[1] = -1;
        b->count = 1;
        b->required = samples[i].mandatory;
        b->risk = samples[i].risk;
    }
    for (int i = 0; i < block_count; i++) {
        blocks[i].options = block_option_count(&blocks[i]);
        order[i] = i;
    }
}

static void sort_order(void) {
    for (int i = 0; i < block_count; i++) {
        for (int j = i + 1; j < block_count; j++) {
            Block *a = &blocks[order[i]];
            Block *b = &blocks[order[j]];
            int swap = 0;
            if (b->required > a->required) swap = 1;
            else if (b->required == a->required) {
                if (b->options < a->options) swap = 1;
                else if (b->options == a->options && b->risk > a->risk) swap = 1;
                else if (b->options == a->options && b->risk == a->risk && b->count > a->count) swap = 1;
            }
            if (swap) {
                int tmp = order[i];
                order[i] = order[j];
                order[j] = tmp;
            }
        }
    }
}

static int block_forbidden_inside(Block *b) {
    if (b->count < 2) return 0;
    const char *left = samples[b->members[0]].id;
    const char *right = samples[b->members[1]].id;
    for (int f = 0; f < forbid_count; f++) {
        if ((strcmp(left, forbid_l[f]) == 0 && strcmp(right, forbid_r[f]) == 0)
            || (strcmp(left, forbid_r[f]) == 0 && strcmp(right, forbid_l[f]) == 0)) {
            return 1;
        }
    }
    return 0;
}

static int can_place(Block *b, int panel_idx) {
    int add_a = 0, add_b = 0, add_slots = b->count;
    if (used_slots[panel_idx] + add_slots > panels[panel_idx].slot_cap) return 0;
    if (b->count == 2 && cohort_separation
        && strcmp(samples[b->members[0]].cohort, samples[b->members[1]].cohort) == 0) {
        return 0;
    }
    if (block_forbidden_inside(b)) return 0;
    for (int m = 0; m < b->count; m++) {
        int idx = b->members[m];
        if (!eligible(idx, panel_idx)) return 0;
        add_a += samples[idx].reagent_a;
        add_b += samples[idx].reagent_b;
        for (int i = 0; i < sample_count; i++) {
            if (assign_now[i] != panel_idx) continue;
            if (cohort_separation && strcmp(samples[i].cohort, samples[idx].cohort) == 0) return 0;
            for (int f = 0; f < forbid_count; f++) {
                if ((strcmp(samples[idx].id, forbid_l[f]) == 0 && strcmp(samples[i].id, forbid_r[f]) == 0)
                    || (strcmp(samples[idx].id, forbid_r[f]) == 0 && strcmp(samples[i].id, forbid_l[f]) == 0)) {
                    return 0;
                }
            }
        }
    }
    if (used_a[panel_idx] + add_a > panels[panel_idx].cap_a) return 0;
    if (used_b[panel_idx] + add_b > panels[panel_idx].cap_b) return 0;
    return 1;
}

static void place_block(Block *b, int panel_idx) {
    for (int m = 0; m < b->count; m++) {
        int idx = b->members[m];
        assign_now[idx] = panel_idx;
        used_slots[panel_idx]++;
        used_a[panel_idx] += samples[idx].reagent_a;
        used_b[panel_idx] += samples[idx].reagent_b;
        assigned_now++;
        risk_now += samples[idx].risk;
    }
}

static void remove_block(Block *b, int panel_idx) {
    for (int m = b->count - 1; m >= 0; m--) {
        int idx = b->members[m];
        risk_now -= samples[idx].risk;
        assigned_now--;
        used_b[panel_idx] -= samples[idx].reagent_b;
        used_a[panel_idx] -= samples[idx].reagent_a;
        used_slots[panel_idx]--;
        assign_now[idx] = -1;
    }
}

static void clear_current_assignment(void) {
    for (int i = 0; i < sample_count; i++) assign_now[i] = -1;
    for (int p = 0; p < panel_count; p++) {
        used_a[p] = 0;
        used_b[p] = 0;
        used_slots[p] = 0;
    }
    assigned_now = 0;
    risk_now = 0;
}

static double clamp(double x) {
    if (x < 0.0) return 0.0;
    if (x > 1.0) return 1.0;
    return x;
}

static int setup_cost(int left_panel, int right_panel) {
    for (int i = 0; i < setup_count; i++) {
        if (strcmp(panels[left_panel].cls, setup_from[i]) == 0
            && strcmp(panels[right_panel].cls, setup_to[i]) == 0) {
            return setup_value[i];
        }
    }
    return 999999;
}

static int build_schedule(int *source_assign);

static void score_leaf(void) {
    int risk = 0, assigned = 0, required_seen[MAX_REQ] = {0}, sentinel_panel[MAX_PANELS] = {0};
    int total_a = 0, total_b = 0, cap_a = 0, cap_b = 0, used_panels = 0, balanced = 0;
    for (int p = 0; p < panel_count; p++) {
        cap_a += panels[p].cap_a;
        cap_b += panels[p].cap_b;
        total_a += used_a[p];
        total_b += used_b[p];
        if (used_slots[p] > 0) {
            used_panels++;
            double la = (double)used_a[p] / panels[p].cap_a;
            double lb = (double)used_b[p] / panels[p].cap_b;
            if (la >= 0.25 && la <= 0.95 && lb >= 0.25 && lb <= 0.95) balanced++;
        }
    }
    for (int i = 0; i < sample_count; i++) {
        if (assign_now[i] < 0) {
            if (samples[i].mandatory) return;
            continue;
        }
        assigned++;
        risk += samples[i].risk;
        for (int r = 0; r < required_count; r++) {
            if (strcmp(samples[i].family, required_families[r]) == 0) required_seen[r] = 1;
        }
        if (in_list(sentinel_families, sentinel_count, samples[i].family)) {
            sentinel_panel[assign_now[i]] = 1;
        }
    }
    if (risk < risk_floor) return;
    int req_hit = 0, sent_hit = 0;
    for (int r = 0; r < required_count; r++) req_hit += required_seen[r];
    if (req_hit < required_count) return;
    for (int p = 0; p < panel_count; p++) sent_hit += sentinel_panel[p];
    if (sent_hit < min_sentinel_panels) return;
    int linked_complete = 0;
    for (int f = 0; f < link_count; f++) {
        int left_panel = -1, right_panel = -1;
        for (int i = 0; i < sample_count; i++) {
            if (strcmp(samples[i].id, link_l[f]) == 0) left_panel = assign_now[i];
            if (strcmp(samples[i].id, link_r[f]) == 0) right_panel = assign_now[i];
        }
        if (left_panel < 0 && right_panel < 0) continue;
        if (left_panel >= 0 && left_panel == right_panel) linked_complete++;
        else return;
    }
    if (linked_complete < linked_pair_floor) return;

    int old_setup_total = best_setup_total;
    int old_len[MAX_PANELS], old_lane[MAX_PANELS][MAX_PANELS];
    for (int l = 0; l < lane_count; l++) {
        old_len[l] = best_sched_len[l];
        for (int i = 0; i < best_sched_len[l]; i++) old_lane[l][i] = best_sched_lane[l][i];
    }
    if (!build_schedule(assign_now)) {
        best_setup_total = old_setup_total;
        for (int l = 0; l < lane_count; l++) {
            best_sched_len[l] = old_len[l];
            for (int i = 0; i < old_len[l]; i++) best_sched_lane[l][i] = old_lane[l][i];
        }
        return;
    }
    int candidate_setup_total = best_setup_total;
    int candidate_len[MAX_PANELS], candidate_lane[MAX_PANELS][MAX_PANELS];
    for (int l = 0; l < lane_count; l++) {
        candidate_len[l] = best_sched_len[l];
        for (int i = 0; i < best_sched_len[l]; i++) candidate_lane[l][i] = best_sched_lane[l][i];
    }

    double risk_score = risk / (double)risk_target;
    if (risk_score > 1.0) risk_score = 1.0;
    double family_score = required_count ? (double)req_hit / required_count : 1.0;
    double load = ((double)total_a / cap_a + (double)total_b / cap_b) / 2.0;
    double reagent_score = clamp(1.0 - ((load > 0.62 ? load - 0.62 : 0.0) * 1.8));
    double coverage_score = (double)assigned / sample_count;
    double stewardship_score = used_panels ? (double)balanced / used_panels : 0.0;
    double sentinel_score = min_sentinel_panels ? (double)sent_hit / min_sentinel_panels : 1.0;
    if (sentinel_score > 1.0) sentinel_score = 1.0;
    double setup_score = clamp(1.0 - ((candidate_setup_total > setup_target ? candidate_setup_total - setup_target : 0.0)
        / (double)(total_setup_cap - setup_target + 1)));

    double total = 0.30 * risk_score + 0.18 * family_score + 0.14 * reagent_score
        + 0.10 * coverage_score + 0.09 * stewardship_score + 0.09 * sentinel_score
        + 0.10 * setup_score;
    double strict = total;
    if (reagent_score < 0.80) strict *= 0.55;
    if (coverage_score < 0.72) strict *= 0.58;
    if (stewardship_score < 0.70) strict *= 0.60;
    if (sentinel_score < 1.0) strict *= 0.50;
    if (setup_score < 1.0) strict *= 0.45;
    if (linked_complete < linked_pair_floor) strict *= 0.40;
    if (strict > best_strict + 1e-12 || (strict > best_strict - 1e-12 && total > best_public)) {
        best_strict = strict;
        best_public = total;
        best_setup_total = candidate_setup_total;
        for (int i = 0; i < sample_count; i++) best_assign[i] = assign_now[i];
        for (int l = 0; l < lane_count; l++) {
            best_sched_len[l] = candidate_len[l];
            for (int i = 0; i < candidate_len[l]; i++) best_sched_lane[l][i] = candidate_lane[l][i];
        }
        if (strict >= 0.93) found_good_solution = 1;
    } else {
        best_setup_total = old_setup_total;
        for (int l = 0; l < lane_count; l++) {
            best_sched_len[l] = old_len[l];
            for (int i = 0; i < old_len[l]; i++) best_sched_lane[l][i] = old_lane[l][i];
        }
    }
}

static int remaining_risk_from(int depth) {
    int total = 0;
    for (int d = depth; d < block_count; d++) {
        total += blocks[order[d]].risk;
    }
    return total;
}

static int remaining_samples_from(int depth) {
    int total = 0;
    for (int d = depth; d < block_count; d++) {
        total += blocks[order[d]].count;
    }
    return total;
}

static void dfs(int depth) {
    if (found_good_solution) return;
    if (risk_now + remaining_risk_from(depth) < risk_floor) return;
    int min_samples = (sample_count * 72 + 99) / 100;
    if (assigned_now + remaining_samples_from(depth) < min_samples) return;
    if (depth == block_count) {
        score_leaf();
        return;
    }
    Block *b = &blocks[order[depth]];
    for (int p = 0; p < panel_count; p++) {
        if (!can_place(b, p)) continue;
        place_block(b, p);
        dfs(depth + 1);
        remove_block(b, p);
    }
    if (!b->required) {
        dfs(depth + 1);
    }
}

static void greedy_seed(void) {
    clear_current_assignment();
    for (int depth = 0; depth < block_count; depth++) {
        Block *b = &blocks[order[depth]];
        int best_panel = -1;
        int best_score = -1000000;
        for (int p = 0; p < panel_count; p++) {
            if (!can_place(b, p)) continue;
            int score = b->risk * 10 - used_slots[p] * 3;
            for (int m = 0; m < b->count; m++) {
                for (int l = 0; l < lane_count; l++) {
                    if (lane_target_family[l][0]
                        && strcmp(samples[b->members[m]].family, lane_target_family[l]) == 0) {
                        score += 20;
                    }
                }
            }
            if (score > best_score) {
                best_score = score;
                best_panel = p;
            }
        }
        if (best_panel >= 0) {
            place_block(b, best_panel);
        } else if (b->required) {
            clear_current_assignment();
            return;
        }
    }
    score_leaf();
}

static int *schedule_assign;

static void collect_active_panels(int *source_assign) {
    active_count = 0;
    for (int p = 0; p < panel_count; p++) {
        int has_sample = 0;
        for (int i = 0; i < sample_count; i++) {
            if (source_assign[i] == p) has_sample = 1;
        }
        if (has_sample) active_panels[active_count++] = p;
    }
}

static void save_schedule(int setup_total) {
    best_setup_total = setup_total;
    for (int l = 0; l < lane_count; l++) {
        best_sched_len[l] = sched_len[l];
        for (int i = 0; i < sched_len[l]; i++) {
            best_sched_lane[l][i] = sched_lane[l][i];
        }
    }
}

static int lane_target_satisfied(int lane_idx) {
    if (!lane_target_family[lane_idx][0]) return 1;
    for (int pos = 0; pos < sched_len[lane_idx]; pos++) {
        int panel_idx = sched_lane[lane_idx][pos];
        for (int s = 0; s < sample_count; s++) {
            if (schedule_assign[s] == panel_idx
                && strcmp(samples[s].family, lane_target_family[lane_idx]) == 0) {
                return 1;
            }
        }
    }
    return 0;
}

static int panel_contains_family(int panel_idx, const char *family) {
    for (int s = 0; s < sample_count; s++) {
        if (schedule_assign[s] == panel_idx && strcmp(samples[s].family, family) == 0) return 1;
    }
    return 0;
}

static int lane_total_setup(int lane_idx) {
    int total = 0;
    for (int i = 1; i < sched_len[lane_idx]; i++) {
        total += setup_cost(sched_lane[lane_idx][i - 1], sched_lane[lane_idx][i]);
    }
    return total;
}

static int greedy_schedule(void) {
    int active_used[MAX_PANELS] = {0};
    int lane_totals[MAX_PANELS] = {0};
    for (int l = 0; l < lane_count; l++) sched_len[l] = best_sched_len[l] = 0;

    for (int l = 0; l < lane_count; l++) {
        if (!lane_target_family[l][0]) continue;
        int choice = -1;
        for (int a = 0; a < active_count; a++) {
            int panel_idx = active_panels[a];
            if (!active_used[a] && panel_contains_family(panel_idx, lane_target_family[l])) {
                choice = a;
                break;
            }
        }
        if (choice < 0) return 0;
        active_used[choice] = 1;
        sched_lane[l][sched_len[l]++] = active_panels[choice];
    }

    for (int pass = 0; pass < 2; pass++) {
        for (int a = 0; a < active_count; a++) {
            if (active_used[a]) continue;
            int panel_idx = active_panels[a];
            int best_lane = -1, best_add = 999999;
            for (int l = 0; l < lane_count; l++) {
                if (sched_len[l] >= max_lane_panels) continue;
                if (pass == 0 && sched_len[l] >= min_lane_panels) continue;
                int add = 0;
                if (sched_len[l] > 0) add = setup_cost(sched_lane[l][sched_len[l] - 1], panel_idx);
                if (lane_totals[l] + add > lane_setup_cap) continue;
                if (add < best_add) {
                    best_add = add;
                    best_lane = l;
                }
            }
            if (best_lane >= 0) {
                sched_lane[best_lane][sched_len[best_lane]++] = panel_idx;
                lane_totals[best_lane] += best_add;
                active_used[a] = 1;
            }
        }
    }

    int total = 0;
    for (int a = 0; a < active_count; a++) {
        if (!active_used[a]) return 0;
    }
    for (int l = 0; l < lane_count; l++) {
        if (sched_len[l] < min_lane_panels || sched_len[l] > max_lane_panels) return 0;
        if (!lane_target_satisfied(l)) return 0;
        total += lane_total_setup(l);
    }
    if (total > total_setup_cap) return 0;
    save_schedule(total);
    return 1;
}

static void schedule_dfs(int placed, int setup_total) {
    if (setup_total > total_setup_cap || setup_total >= best_setup_total) return;
    if (placed == active_count) {
        for (int l = 0; l < lane_count; l++) {
            if (sched_len[l] < min_lane_panels || sched_len[l] > max_lane_panels) return;
            if (!lane_target_satisfied(l)) return;
        }
        save_schedule(setup_total);
        return;
    }
    for (int a = 0; a < active_count; a++) {
        if (sched_used[a]) continue;
        int panel_idx = active_panels[a];
        for (int l = 0; l < lane_count; l++) {
            if (sched_len[l] >= max_lane_panels) continue;
            int add = 0;
            if (sched_len[l] > 0) {
                add = setup_cost(sched_lane[l][sched_len[l] - 1], panel_idx);
            }
            if (add >= 999999) continue;
            int lane_total = 0;
            for (int i = 1; i < sched_len[l]; i++) {
                lane_total += setup_cost(sched_lane[l][i - 1], sched_lane[l][i]);
            }
            if (lane_total + add > lane_setup_cap) continue;
            sched_used[a] = 1;
            sched_lane[l][sched_len[l]++] = panel_idx;
            schedule_dfs(placed + 1, setup_total + add);
            sched_len[l]--;
            sched_used[a] = 0;
        }
    }
}

static int build_schedule(int *source_assign) {
    schedule_assign = source_assign;
    collect_active_panels(source_assign);
    if (active_count == 0) return 0;
    if (lane_count > MAX_PANELS) return 0;
    for (int l = 0; l < lane_count; l++) {
        sched_len[l] = best_sched_len[l] = 0;
    }
    for (int i = 0; i < active_count; i++) sched_used[i] = 0;
    best_setup_total = 999999;
    if (greedy_schedule()) return 1;
    schedule_dfs(0, 0);
    return best_setup_total <= total_setup_cap;
}

static int write_output(const char *out_dir) {
    mkdir(out_dir, 0777);
    char path[LINE];
    snprintf(path, sizeof(path), "%s/batches.json", out_dir);
    FILE *fh = fopen(path, "w");
    if (!fh) return 0;
    fprintf(fh, "{\n  \"panels\": [\n");
    int emitted = 0;
    for (int p = 0; p < panel_count; p++) {
        int count = 0;
        for (int i = 0; i < sample_count; i++) {
            if (best_assign[i] == p) count++;
        }
        if (!count) continue;
        if (emitted) fprintf(fh, ",\n");
        emitted = 1;
        fprintf(fh, "    {\"panel_id\":\"%s\",\"sample_ids\":[", panels[p].id);
        int first = 1;
        for (int i = 0; i < sample_count; i++) {
            if (best_assign[i] == p) {
                if (!first) fprintf(fh, ",");
                first = 0;
                fprintf(fh, "\"%s\"", samples[i].id);
            }
        }
        fprintf(fh, "]}");
    }
    fprintf(fh, "\n  ],\n  \"runs\": [\n");
    for (int l = 0; l < lane_count; l++) {
        if (l) fprintf(fh, ",\n");
        fprintf(fh, "    {\"lane\":\"L%d\",\"panel_ids\":[", l + 1);
        for (int i = 0; i < best_sched_len[l]; i++) {
            if (i) fprintf(fh, ",");
            fprintf(fh, "\"%s\"", panels[best_sched_lane[l][i]].id);
        }
        fprintf(fh, "]}");
    }
    fprintf(fh, "\n  ]\n}\n");
    fclose(fh);
    return 1;
}

int main(int argc, char **argv) {
    const char *input_dir = argc > 1 ? argv[1] : "/app/task_file/input_data";
    const char *output_dir = argc > 2 ? argv[2] : "/app/task_file/output_data";
    char path[LINE];
    snprintf(path, sizeof(path), "%s/config.txt", input_dir);
    load_config(path);
    snprintf(path, sizeof(path), "%s/samples.tsv", input_dir);
    load_samples(path);
    snprintf(path, sizeof(path), "%s/panels.tsv", input_dir);
    load_panels(path);
    for (int i = 0; i < sample_count; i++) {
        assign_now[i] = best_assign[i] = -1;
    }
    build_blocks();
    sort_order();
    greedy_seed();
    if (!found_good_solution) {
        clear_current_assignment();
        dfs(0);
    }
    if (best_strict < 0.0) return 3;
    if (best_setup_total > total_setup_cap) return 5;
    if (!write_output(output_dir)) return 4;
    return 0;
}
