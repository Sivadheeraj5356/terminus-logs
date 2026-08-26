#include "ac_io.h"
#include "ac_json.h"
#include "ac_lane.h"

#include <dirent.h>
#include <sys/stat.h>

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

static int ensure_dir(const char *path) {
    struct stat st;
    if (stat(path, &st) == 0) {
        return S_ISDIR(st.st_mode) ? 0 : -1;
    }
    return mkdir(path, 0755);
}

static int basename_no_ext(const char *path, char *out, int outlen) {
    const char *slash = strrchr(path, '/');
    const char *name = slash ? slash + 1 : path;
    strncpy(out, name, outlen - 1);
    out[outlen - 1] = '\0';
    char *dot = strrchr(out, '.');
    if (dot) {
        *dot = '\0';
    }
    return 0;
}

static int run_batch(const char *ct_dir, const char *out_dir) {
    DIR *dir = opendir(ct_dir);
    if (!dir) {
        return -1;
    }
    ensure_dir(out_dir);
    std::vector<std::string> profiles;
    struct dirent *ent;
    while ((ent = readdir(dir)) != nullptr) {
        if (ent->d_name[0] == '.') {
            continue;
        }
        const char *dot = strrchr(ent->d_name, '.');
        if (!dot || strcmp(dot, ".ctb") != 0) {
            continue;
        }
        char ct_path[512];
        snprintf(ct_path, sizeof ct_path, "%s/%s", ct_dir, ent->d_name);
        char profile[AC_MAX_PROFILE];
        basename_no_ext(ent->d_name, profile, sizeof profile);
        ac_ct_volume vol;
        ac_speed_map speed;
        ac_fdtd_state state;
        if (ac_lane_prepare(ct_path, &vol, &speed, &state) != 0) {
            closedir(dir);
            return -1;
        }
        ac_formant_report rep;
        if (ac_lane_finalize(profile, &state.trace, &rep) != 0) {
            closedir(dir);
            return -1;
        }
        char prof_dir[512];
        snprintf(prof_dir, sizeof prof_dir, "%s/%s", out_dir, profile);
        ensure_dir(prof_dir);
        char report_path[512];
        snprintf(report_path, sizeof report_path, "%s/formants.json", prof_dir);
        if (ac_write_formant_json(report_path, &rep) != 0) {
            closedir(dir);
            return -1;
        }
        char wav_path[512];
        snprintf(wav_path, sizeof wav_path, "%s/pressure.wav", prof_dir);
        ac_write_pressure_wav(wav_path, &state.trace, rep.sample_rate_hz);
        profiles.emplace_back(profile);
    }
    closedir(dir);
    if (profiles.empty()) {
        return -1;
    }
    std::sort(profiles.begin(), profiles.end());
    std::vector<const char *> names;
    for (auto &p : profiles) {
        names.push_back(p.c_str());
    }
    char summary_path[512];
    snprintf(summary_path, sizeof summary_path, "%s/summary.json", out_dir);
    return ac_write_summary_json(summary_path, names.data(), static_cast<int>(names.size()));
}

int main(int argc, char **argv) {
    if (argc >= 2 && strcmp(argv[1], "batch") == 0) {
        const char *ct = "/app/data/ct";
        const char *out = "/app/output/reports";
        for (int i = 2; i + 1 < argc; ++i) {
            if (strcmp(argv[i], "--ct") == 0) {
                ct = argv[++i];
            } else if (strcmp(argv[i], "--out") == 0) {
                out = argv[++i];
            }
        }
        return run_batch(ct, out) == 0 ? 0 : 1;
    }
    fprintf(stderr, "usage: reso_sim batch --ct DIR --out DIR\n");
    return 1;
}
