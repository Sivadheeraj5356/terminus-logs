#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define FRAME_SIZE 36
#define MAX_KEYS 4096
#define NO_SEQ 65535u
#define SEQ_FORWARD_LIMIT 257u

typedef struct {
    int used;
    uint8_t station;
    uint16_t sensor;
    int has_data_seq;
    uint16_t data_seq;
    int has_cal_seq;
    uint16_t cal_seq;
    int active;
    int32_t raw;
    int64_t timestamp;
    int32_t scale_ppm;
    int32_t offset_milli;
    uint16_t cal_key;
    uint16_t data_key;
} KeyState;

typedef struct {
    int has_seq;
    uint16_t seq;
    uint16_t auth_key;
    int has_anchor_seq;
    int anchor_current;
    uint16_t anchor_seq;
    uint16_t epoch_key;
    int has_relay_seq;
    int relay_current;
    uint16_t relay_seq;
    uint16_t relay_key;
    int has_checkpoint_seq;
    int checkpoint_current;
    uint16_t checkpoint_seq;
    uint16_t checkpoint_key;
    int has_quorum_seq;
    int quorum_current;
    uint16_t quorum_seq;
    uint16_t quorum_key;
    uint8_t quorum_witness_a;
    uint8_t quorum_witness_b;
    uint16_t quorum_beacon_seq;
    uint16_t quorum_anchor_seq;
    uint16_t quorum_checkpoint_seq;
    uint16_t witness_a_seq;
    uint16_t witness_b_seq;
    int64_t timestamp;
} StationState;

typedef struct {
    long long accepted;
    long long bad_length;
    long long bad_magic;
    long long bad_crc;
    long long bad_version;
    long long bad_flags;
    long long bad_type;
    long long bad_layout;
    long long stale;
    long long dependency;
} Counts;

static uint32_t crc32_ieee(const unsigned char *buf, size_t len) {
    uint32_t crc = 0xffffffffu;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint32_t)buf[i];
        for (int bit = 0; bit < 8; bit++) {
            uint32_t mask = 0u - (crc & 1u);
            crc = (crc >> 1) ^ (0xedb88320u & mask);
        }
    }
    return crc ^ 0xffffffffu;
}

static uint16_t le16(const unsigned char *p) {
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static uint32_t le32u(const unsigned char *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static int32_t le32s(const unsigned char *p) {
    return (int32_t)le32u(p);
}

static int64_t le64s(const unsigned char *p) {
    uint64_t v = 0;
    for (int i = 7; i >= 0; i--) {
        v = (v << 8) | (uint64_t)p[i];
    }
    return (int64_t)v;
}

static int is_newer(uint16_t candidate, uint16_t current) {
    uint16_t d = (uint16_t)(candidate - current);
    return d >= 1u && d <= SEQ_FORWARD_LIMIT;
}

static void decode_beacon_x(unsigned char *frame) {
    uint8_t version = frame[2];
    uint8_t type = frame[3];
    uint8_t station = frame[5];
    uint8_t state = (uint8_t)(0xa5u ^ station ^ (uint8_t)(type * 17u) ^ version);

    for (int off = 6; off <= 31; off++) {
        state = (uint8_t)((uint8_t)(state << 1) | (uint8_t)(state >> 7));
        state = (uint8_t)(state ^ (uint8_t)(0x3du + (unsigned)off * 11u));
        frame[off] = (unsigned char)(frame[off] ^ state);
    }
}

static int beacon_dependency_ok(const StationState *stations, uint8_t station, int32_t scale_ppm) {
    const StationState *st = &stations[station];
    uint16_t tag = (uint16_t)((uint32_t)scale_ppm & 0xffffu);
    return st->has_seq && st->seq == tag;
}

static uint16_t rotl16(uint16_t v, unsigned n) {
    n &= 15u;
    return (uint16_t)((uint16_t)(v << n) | (uint16_t)(v >> (16u - n)));
}

static uint32_t beacon_auth_word(uint8_t station, uint16_t seq, uint16_t base_seq,
                                 int64_t timestamp) {
    uint32_t tlo = (uint32_t)((uint64_t)timestamp & 0xffffffffu);
    uint32_t v = 0x5f3759dfu ^ tlo;
    v += (uint32_t)seq * 1103515245u;
    v ^= (uint32_t)station * 2654435761u;
    v += (uint32_t)base_seq * 40503u;
    return v;
}

static uint16_t beacon_auth_key(uint8_t station, uint16_t seq, uint16_t base_seq,
                                int64_t timestamp) {
    uint16_t tlo = (uint16_t)((uint64_t)timestamp & 0xffffu);
    return (uint16_t)(rotl16(seq, 5) ^ tlo ^ base_seq ^ ((uint16_t)station << 8));
}

static uint32_t anchor_auth_word(uint8_t station, uint16_t seq, uint16_t base_seq,
                                 int64_t timestamp, uint16_t station_key) {
    uint32_t tlo = (uint32_t)((uint64_t)timestamp & 0xffffffffu);
    uint32_t v = 0xc2b2ae35u ^ tlo;
    v += (uint32_t)seq * 747796405u;
    v ^= (uint32_t)station_key * 2891336453u;
    v += (uint32_t)station * 40503u;
    v += (uint32_t)base_seq * 97u;
    return v;
}

static uint16_t anchor_epoch_key(uint8_t station, uint16_t seq, uint16_t base_seq,
                                 int64_t timestamp, uint16_t station_key) {
    return (uint16_t)(rotl16(seq, 9) ^
                      station_key ^
                      (uint16_t)((uint64_t)timestamp & 0xffffu) ^
                      base_seq ^
                      ((uint16_t)station << 8));
}

static uint32_t relay_auth_word(uint8_t station, uint8_t source_station, uint16_t seq,
                                uint16_t base_seq, int64_t timestamp,
                                uint16_t epoch_key, uint16_t source_key) {
    uint32_t tlo = (uint32_t)((uint64_t)timestamp & 0xffffffffu);
    uint32_t v = 0x85ebca6bu ^ tlo;
    v += (uint32_t)seq * 1597334677u;
    v ^= (uint32_t)epoch_key * 2246822519u;
    v += (uint32_t)source_key * 3266489917u;
    v ^= (uint32_t)station * 40503u;
    v += (uint32_t)source_station * 97u;
    v += (uint32_t)base_seq * 31u;
    return v;
}

static uint16_t relay_key(uint8_t station, uint8_t source_station, uint16_t seq,
                          int64_t timestamp, uint16_t epoch_key, uint16_t source_key) {
    return (uint16_t)(rotl16(seq, 2) ^
                      epoch_key ^
                      source_key ^
                      (uint16_t)((uint64_t)timestamp & 0xffffu) ^
                      ((uint16_t)station << 8) ^
                      source_station);
}

static uint32_t checkpoint_auth_word(uint8_t station, uint16_t seq, uint16_t base_seq,
                                     int64_t timestamp, uint16_t station_key,
                                     uint16_t epoch_key) {
    uint32_t v = 0x27d4eb2fu ^ (uint32_t)((uint64_t)timestamp & 0xffffffffu);
    v += (uint32_t)seq * 2654435761u;
    v ^= (uint32_t)station_key * 2246822519u;
    v += (uint32_t)epoch_key * 3266489917u;
    v ^= (uint32_t)station * 668265263u;
    v += (uint32_t)base_seq * 40503u;
    return v;
}

static uint16_t checkpoint_key(uint8_t station, uint16_t seq, uint16_t base_seq,
                               int64_t timestamp, uint16_t station_key,
                               uint16_t epoch_key) {
    return (uint16_t)(rotl16(seq, 13) ^ station_key ^ rotl16(epoch_key, 3) ^
                      (uint16_t)((uint64_t)timestamp & 0xffffu) ^ base_seq ^
                      ((uint16_t)station << 8));
}

static uint32_t quorum_auth_word(uint8_t station, uint16_t witnesses, uint16_t seq,
                                 uint16_t base_seq, int64_t timestamp,
                                 uint16_t station_key, uint16_t epoch_key,
                                 uint16_t checkpoint_key_value,
                                 uint16_t witness_a_key, uint16_t witness_b_key) {
    uint32_t v = 0x165667b1u ^ (uint32_t)((uint64_t)timestamp & 0xffffffffu);
    v += (uint32_t)seq * 374761393u;
    v ^= (uint32_t)checkpoint_key_value * 668265263u;
    v += (uint32_t)station_key * 2246822519u;
    v ^= (uint32_t)epoch_key * 3266489917u;
    v += (uint32_t)witness_a_key * 40503u;
    v ^= (uint32_t)witness_b_key * 2654435761u;
    v += (uint32_t)witnesses * 97u;
    v += (uint32_t)base_seq * 31u;
    v ^= (uint32_t)station * 1597334677u;
    return v;
}

static uint16_t quorum_key(uint8_t station, uint16_t witnesses, uint16_t seq,
                           int64_t timestamp, uint16_t station_key,
                           uint16_t epoch_key, uint16_t checkpoint_key_value,
                           uint16_t witness_a_key, uint16_t witness_b_key) {
    return (uint16_t)(rotl16(seq, 7) ^ station_key ^ epoch_key ^ checkpoint_key_value ^
                      rotl16(witness_a_key, 3) ^ rotl16(witness_b_key, 11) ^
                      (uint16_t)((uint64_t)timestamp & 0xffffu) ^ witnesses ^
                      ((uint16_t)station << 8));
}

static uint32_t calibration_auth_word(uint8_t station, uint16_t sensor, uint16_t seq,
                                      uint16_t base_seq, int32_t scale_ppm,
                                      int32_t offset_milli, int64_t timestamp,
                                      uint16_t station_key) {
    uint32_t v = 0x9e3779b9u ^ (uint32_t)((uint64_t)timestamp & 0xffffffffu);
    v += (uint32_t)seq * 2246822519u;
    v ^= (uint32_t)station_key * 3266489917u;
    v += (uint32_t)sensor * 668265263u;
    v ^= (uint32_t)scale_ppm * 40503u;
    v += (uint32_t)offset_milli ^ (uint32_t)rotl16(base_seq, 7);
    v ^= (uint32_t)station * 2654435761u;
    return v;
}

static int carry_dependency_ok(const StationState *stations, uint8_t station,
                               uint16_t seq, uint16_t sensor, int32_t offset_milli) {
    const StationState *st = &stations[station];
    if (!st->has_seq) {
        return 0;
    }
    uint16_t tag = (uint16_t)(((uint32_t)offset_milli >> 16) & 0xffffu);
    uint16_t want = (uint16_t)(st->auth_key ^ rotl16(seq, 3) ^ sensor);
    return tag == want;
}

static int epoch_dependency_ok(const StationState *stations, uint8_t station,
                               uint16_t seq, uint16_t sensor, int64_t timestamp) {
    const StationState *st = &stations[station];
    if (!st->anchor_current) {
        return 0;
    }
    uint16_t tag = (uint16_t)(((uint64_t)timestamp >> 48) & 0xffffu);
    uint16_t want = (uint16_t)(st->epoch_key ^ rotl16(seq, 6) ^ sensor);
    return tag == want;
}

static int relay_dependency_ok(const StationState *stations, uint8_t station,
                               uint16_t seq, uint16_t sensor, int64_t timestamp) {
    const StationState *st = &stations[station];
    if (!st->relay_current) {
        return 0;
    }
    uint16_t tag = (uint16_t)(((uint64_t)timestamp >> 32) & 0xffffu);
    uint16_t want = (uint16_t)(st->relay_key ^ rotl16(seq, 9) ^ sensor);
    return tag == want;
}

static int checkpoint_dependency_ok(const StationState *stations, uint8_t station,
                                    uint16_t seq, uint16_t sensor, int64_t timestamp) {
    const StationState *st = &stations[station];
    if (!st->checkpoint_current) {
        return 0;
    }
    uint16_t tag = (uint16_t)(((uint64_t)timestamp >> 16) & 0xffffu);
    uint16_t want = (uint16_t)(st->checkpoint_key ^ rotl16(seq, 12) ^ sensor);
    return tag == want;
}

static int quorum_dependency_ok(const StationState *stations, uint8_t station,
                                uint16_t seq, uint16_t sensor, int64_t timestamp) {
    const StationState *st = &stations[station];
    if (!st->quorum_current || !st->has_seq || !st->anchor_current ||
        !st->checkpoint_current || st->seq != st->quorum_beacon_seq ||
        st->anchor_seq != st->quorum_anchor_seq ||
        st->checkpoint_seq != st->quorum_checkpoint_seq) {
        return 0;
    }
    const StationState *a = &stations[st->quorum_witness_a];
    const StationState *b = &stations[st->quorum_witness_b];
    if (!a->has_seq || !b->has_seq || a->seq != st->witness_a_seq ||
        b->seq != st->witness_b_seq) {
        return 0;
    }
    uint16_t tag = (uint16_t)((uint64_t)timestamp & 0xffffu);
    uint16_t want = (uint16_t)(st->quorum_key ^ rotl16(seq, 15) ^ sensor);
    return tag == want;
}

static uint16_t calibration_key(uint8_t station, uint16_t sensor, uint16_t seq,
                                int32_t scale_ppm, int32_t offset_milli) {
    uint32_t scale = (uint32_t)scale_ppm;
    uint32_t offset = (uint32_t)offset_milli;
    return (uint16_t)(rotl16(seq, 7) ^
                      (uint16_t)(scale & 0xffffu) ^
                      (uint16_t)((scale >> 16) & 0xffffu) ^
                      rotl16((uint16_t)(offset & 0xffffu), 3) ^
                      (uint16_t)((offset >> 16) & 0xffffu) ^
                      ((uint16_t)station << 8) ^
                      sensor);
}

static uint16_t calibration_tag(uint16_t cal_key, uint16_t seq) {
    return (uint16_t)(cal_key ^ rotl16(seq, 1));
}

static int calibration_dependency_ok(const KeyState *k, uint16_t seq, int32_t scale_ppm) {
    if (!k->has_cal_seq) {
        return 0;
    }
    uint16_t tag = (uint16_t)(((uint32_t)scale_ppm >> 16) & 0xffffu);
    return tag == calibration_tag(k->cal_key, seq);
}

static uint16_t chain_tag(uint16_t data_key, uint16_t base_seq, uint16_t sensor) {
    return (uint16_t)(data_key ^ rotl16(base_seq, 5) ^ sensor);
}

static int chain_dependency_ok(const KeyState *k, uint16_t base_seq, uint16_t sensor,
                               int32_t offset_milli) {
    uint16_t tag = (uint16_t)((uint32_t)offset_milli & 0xffffu);
    return tag == chain_tag(k->data_key, base_seq, sensor);
}

static uint16_t snapshot_data_key(uint16_t station_key, uint16_t cal_key, uint8_t station,
                                  uint16_t sensor, uint16_t seq, int32_t raw,
                                  int64_t timestamp) {
    return (uint16_t)(station_key ^
                      cal_key ^
                      (uint16_t)((uint32_t)raw & 0xffffu) ^
                      rotl16(seq, 4) ^
                      (uint16_t)((uint64_t)timestamp & 0xffffu) ^
                      ((uint16_t)station << 8) ^
                      sensor);
}

static uint16_t delta_data_key(uint16_t old_key, uint16_t seq, int32_t raw_delta,
                               int64_t timestamp) {
    return (uint16_t)(rotl16(old_key, 3) ^
                      (uint16_t)((uint32_t)raw_delta & 0xffffu) ^
                      seq ^
                      (uint16_t)((uint64_t)timestamp & 0xffffu));
}

static uint16_t delete_data_key(uint16_t old_key, uint16_t seq, int64_t timestamp) {
    return (uint16_t)(rotl16(old_key, 11) ^
                      seq ^
                      (uint16_t)((uint64_t)timestamp & 0xffffu) ^
                      0xd1e7u);
}

static KeyState *find_key(KeyState *keys, size_t *nkeys, uint8_t station, uint16_t sensor) {
    for (size_t i = 0; i < *nkeys; i++) {
        if (keys[i].station == station && keys[i].sensor == sensor) {
            return &keys[i];
        }
    }
    if (*nkeys >= MAX_KEYS) {
        return NULL;
    }
    KeyState *k = &keys[*nkeys];
    memset(k, 0, sizeof(*k));
    k->used = 1;
    k->station = station;
    k->sensor = sensor;
    k->scale_ppm = 1000000;
    k->offset_milli = 0;
    (*nkeys)++;
    return k;
}

static int active_cmp(const void *a, const void *b) {
    const KeyState *ka = *(const KeyState * const *)a;
    const KeyState *kb = *(const KeyState * const *)b;
    if (ka->station != kb->station) {
        return (int)ka->station - (int)kb->station;
    }
    if (ka->sensor < kb->sensor) return -1;
    if (ka->sensor > kb->sensor) return 1;
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: %s <frames_file>\n", argv[0]);
        return 2;
    }

    FILE *f = fopen(argv[1], "rb");
    if (!f) {
        fprintf(stderr, "open %s: %s\n", argv[1], strerror(errno));
        return 2;
    }

    KeyState keys[MAX_KEYS];
    memset(keys, 0, sizeof(keys));
    StationState stations[256];
    memset(stations, 0, sizeof(stations));
    size_t nkeys = 0;
    Counts counts;
    memset(&counts, 0, sizeof(counts));

    unsigned char frame[FRAME_SIZE];
    for (;;) {
        size_t got = fread(frame, 1, FRAME_SIZE, f);
        if (got == 0) {
            if (ferror(f)) {
                fclose(f);
                return 2;
            }
            break;
        }
        if (got < FRAME_SIZE) {
            counts.bad_length++;
            break;
        }

        if (frame[0] != 0x48 || frame[1] != 0x42) {
            counts.bad_magic++;
            continue;
        }

        uint32_t want_crc = le32u(frame + 32);
        uint32_t got_crc = crc32_ieee(frame, 32);
        if (want_crc != got_crc) {
            counts.bad_crc++;
            continue;
        }

        uint8_t version = frame[2];
        uint8_t type = frame[3];
        uint8_t flags = frame[4];
        uint8_t station = frame[5];
        uint16_t seq = le16(frame + 6);
        uint16_t sensor = le16(frame + 8);
        uint16_t base_seq = le16(frame + 10);
        int32_t raw = le32s(frame + 12);
        int32_t scale_ppm = le32s(frame + 16);
        int32_t offset_milli = le32s(frame + 20);
        int64_t timestamp = le64s(frame + 24);

        if (version != 1 && version != 2) {
            counts.bad_version++;
            continue;
        }
        if ((version == 1 && flags != 0) ||
            (version == 2 && ((flags & 0x80u) != 0 || (((flags & 0x7eu) != 0) && ((flags & 1u) == 0))))) {
            counts.bad_flags++;
            continue;
        }
        if (type < 1 || type > 9) {
            counts.bad_type++;
            continue;
        }

        if ((flags & 1u) != 0) {
            decode_beacon_x(frame);
            seq = le16(frame + 6);
            sensor = le16(frame + 8);
            base_seq = le16(frame + 10);
            raw = le32s(frame + 12);
            scale_ppm = le32s(frame + 16);
            offset_milli = le32s(frame + 20);
            timestamp = le64s(frame + 24);
        }

        if (type == 5) {
            if (version != 2 || flags != 1u || sensor != 0 ||
                (uint32_t)raw != beacon_auth_word(station, seq, base_seq, timestamp)) {
                counts.bad_layout++;
                continue;
            }
            StationState *st = &stations[station];
            if (st->has_seq && !is_newer(seq, st->seq)) {
                counts.stale++;
                continue;
            }
            st->has_seq = 1;
            st->seq = seq;
            st->auth_key = beacon_auth_key(station, seq, base_seq, timestamp);
            st->timestamp = timestamp;
            st->anchor_current = 0;
            st->relay_current = 0;
            st->checkpoint_current = 0;
            st->quorum_current = 0;
            counts.accepted++;
            continue;
        }

        if (type == 6) {
            if (version != 2 || flags != 1u || sensor != 0) {
                counts.bad_layout++;
                continue;
            }
            StationState *st = &stations[station];
            if (st->has_anchor_seq && !is_newer(seq, st->anchor_seq)) {
                counts.stale++;
                continue;
            }
            if (!st->has_seq || st->seq != base_seq ||
                (uint32_t)raw != anchor_auth_word(station, seq, base_seq, timestamp, st->auth_key)) {
                counts.dependency++;
                continue;
            }
            st->has_anchor_seq = 1;
            st->anchor_current = 1;
            st->anchor_seq = seq;
            st->epoch_key = anchor_epoch_key(station, seq, base_seq, timestamp, st->auth_key);
            st->timestamp = timestamp;
            st->relay_current = 0;
            st->checkpoint_current = 0;
            st->quorum_current = 0;
            counts.accepted++;
            continue;
        }

        if (type == 7) {
            if (version != 2 || flags != 1u || sensor > 255u) {
                counts.bad_layout++;
                continue;
            }
            uint8_t source_station = (uint8_t)sensor;
            StationState *st = &stations[station];
            StationState *src = &stations[source_station];
            if (st->has_relay_seq && !is_newer(seq, st->relay_seq)) {
                counts.stale++;
                continue;
            }
            if (!st->anchor_current || st->anchor_seq != base_seq ||
                !src->has_seq ||
                (uint32_t)raw != relay_auth_word(station, source_station, seq, base_seq,
                                                 timestamp, st->epoch_key, src->auth_key)) {
                counts.dependency++;
                continue;
            }
            st->has_relay_seq = 1;
            st->relay_current = 1;
            st->relay_seq = seq;
            st->relay_key = relay_key(station, source_station, seq, timestamp,
                                      st->epoch_key, src->auth_key);
            st->timestamp = timestamp;
            st->checkpoint_current = 0;
            st->quorum_current = 0;
            counts.accepted++;
            continue;
        }

        if (type == 8) {
            if (version != 2 || flags != 1u || sensor != 0) {
                counts.bad_layout++;
                continue;
            }
            StationState *st = &stations[station];
            if (st->has_checkpoint_seq && !is_newer(seq, st->checkpoint_seq)) {
                counts.stale++;
                continue;
            }
            if (!st->has_seq || !st->anchor_current || st->anchor_seq != base_seq ||
                (uint32_t)raw != checkpoint_auth_word(station, seq, base_seq, timestamp,
                                                       st->auth_key, st->epoch_key)) {
                counts.dependency++;
                continue;
            }
            st->has_checkpoint_seq = 1;
            st->checkpoint_current = 1;
            st->checkpoint_seq = seq;
            st->checkpoint_key = checkpoint_key(station, seq, base_seq, timestamp,
                                                 st->auth_key, st->epoch_key);
            st->quorum_current = 0;
            counts.accepted++;
            continue;
        }

        if (type == 9) {
            uint8_t witness_a = (uint8_t)(sensor & 0xffu);
            uint8_t witness_b = (uint8_t)(sensor >> 8);
            if (version != 2 || flags != 1u || witness_a >= witness_b ||
                witness_a == station || witness_b == station) {
                counts.bad_layout++;
                continue;
            }
            StationState *st = &stations[station];
            StationState *a = &stations[witness_a];
            StationState *b = &stations[witness_b];
            if (st->has_quorum_seq && !is_newer(seq, st->quorum_seq)) {
                counts.stale++;
                continue;
            }
            uint16_t tagged_a_seq = (uint16_t)((uint32_t)scale_ppm & 0xffffu);
            uint16_t tagged_b_seq = (uint16_t)(((uint32_t)scale_ppm >> 16) & 0xffffu);
            uint16_t tagged_anchor = (uint16_t)((uint32_t)offset_milli & 0xffffu);
            uint16_t tagged_beacon = (uint16_t)(((uint32_t)offset_milli >> 16) & 0xffffu);
            if (!st->has_seq || !st->anchor_current || !st->checkpoint_current ||
                st->checkpoint_seq != base_seq || st->anchor_seq != tagged_anchor ||
                st->seq != tagged_beacon || !a->has_seq || !b->has_seq ||
                a->seq != tagged_a_seq || b->seq != tagged_b_seq ||
                (uint32_t)raw != quorum_auth_word(station, sensor, seq, base_seq, timestamp,
                                                  st->auth_key, st->epoch_key,
                                                  st->checkpoint_key, a->auth_key,
                                                  b->auth_key)) {
                counts.dependency++;
                continue;
            }
            st->has_quorum_seq = 1;
            st->quorum_current = 1;
            st->quorum_seq = seq;
            st->quorum_key = quorum_key(station, sensor, seq, timestamp, st->auth_key,
                                        st->epoch_key, st->checkpoint_key,
                                        a->auth_key, b->auth_key);
            st->quorum_witness_a = witness_a;
            st->quorum_witness_b = witness_b;
            st->quorum_beacon_seq = st->seq;
            st->quorum_anchor_seq = st->anchor_seq;
            st->quorum_checkpoint_seq = st->checkpoint_seq;
            st->witness_a_seq = a->seq;
            st->witness_b_seq = b->seq;
            counts.accepted++;
            continue;
        }

        if ((flags & 0x7eu) != 0 && type == 1) {
            counts.bad_layout++;
            continue;
        }

        KeyState *k = find_key(keys, &nkeys, station, sensor);
        if (!k) {
            return 2;
        }

        if (type == 1) {
            if (k->has_cal_seq && !is_newer(seq, k->cal_seq)) {
                counts.stale++;
                continue;
            }
            if ((flags & 1u) != 0) {
                StationState *st = &stations[station];
                if (!st->has_seq || st->seq != base_seq ||
                    (uint32_t)raw != calibration_auth_word(station, sensor, seq, base_seq,
                                                           scale_ppm, offset_milli,
                                                           timestamp, st->auth_key)) {
                    counts.dependency++;
                    continue;
                }
            }
            k->has_cal_seq = 1;
            k->cal_seq = seq;
            k->scale_ppm = scale_ppm;
            k->offset_milli = offset_milli;
            k->cal_key = calibration_key(station, sensor, seq, scale_ppm, offset_milli);
            counts.accepted++;
        } else if (type == 2) {
            if (k->has_data_seq && !is_newer(seq, k->data_seq)) {
                counts.stale++;
                continue;
            }
            if ((flags & 1u) != 0 && !beacon_dependency_ok(stations, station, scale_ppm)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 4u) != 0 && !calibration_dependency_ok(k, seq, scale_ppm)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 2u) != 0 &&
                !carry_dependency_ok(stations, station, seq, sensor, offset_milli)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 8u) != 0 &&
                !epoch_dependency_ok(stations, station, seq, sensor, timestamp)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 16u) != 0 &&
                !relay_dependency_ok(stations, station, seq, sensor, timestamp)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 32u) != 0 &&
                !checkpoint_dependency_ok(stations, station, seq, sensor, timestamp)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 64u) != 0 &&
                !quorum_dependency_ok(stations, station, seq, sensor, timestamp)) {
                counts.dependency++;
                continue;
            }
            k->has_data_seq = 1;
            k->data_seq = seq;
            k->active = 1;
            k->raw = raw;
            k->timestamp = timestamp;
            k->data_key = snapshot_data_key(stations[station].has_seq ? stations[station].auth_key : 0,
                                            k->cal_key, station, sensor, seq, raw, timestamp);
            counts.accepted++;
        } else if (type == 3) {
            if (k->has_data_seq && !is_newer(seq, k->data_seq)) {
                counts.stale++;
                continue;
            }
            if (!k->active || !k->has_data_seq || base_seq != k->data_seq) {
                counts.dependency++;
                continue;
            }
            if ((flags & 1u) != 0 && !beacon_dependency_ok(stations, station, scale_ppm)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 4u) != 0 && !calibration_dependency_ok(k, seq, scale_ppm)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 2u) != 0 &&
                !carry_dependency_ok(stations, station, seq, sensor, offset_milli)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 4u) != 0 &&
                !chain_dependency_ok(k, base_seq, sensor, offset_milli)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 8u) != 0 &&
                !epoch_dependency_ok(stations, station, seq, sensor, timestamp)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 16u) != 0 &&
                !relay_dependency_ok(stations, station, seq, sensor, timestamp)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 32u) != 0 &&
                !checkpoint_dependency_ok(stations, station, seq, sensor, timestamp)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 64u) != 0 &&
                !quorum_dependency_ok(stations, station, seq, sensor, timestamp)) {
                counts.dependency++;
                continue;
            }
            uint16_t old_key = k->data_key;
            k->raw += raw;
            k->data_seq = seq;
            k->timestamp = timestamp;
            k->data_key = delta_data_key(old_key, seq, raw, timestamp);
            counts.accepted++;
        } else {
            if (k->has_data_seq && !is_newer(seq, k->data_seq)) {
                counts.stale++;
                continue;
            }
            if (base_seq != NO_SEQ && (!k->has_data_seq || base_seq != k->data_seq)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 1u) != 0 && !beacon_dependency_ok(stations, station, scale_ppm)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 4u) != 0 && !calibration_dependency_ok(k, seq, scale_ppm)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 2u) != 0 &&
                !carry_dependency_ok(stations, station, seq, sensor, offset_milli)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 4u) != 0 && base_seq != NO_SEQ &&
                !chain_dependency_ok(k, base_seq, sensor, offset_milli)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 8u) != 0 &&
                !epoch_dependency_ok(stations, station, seq, sensor, timestamp)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 16u) != 0 &&
                !relay_dependency_ok(stations, station, seq, sensor, timestamp)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 32u) != 0 &&
                !checkpoint_dependency_ok(stations, station, seq, sensor, timestamp)) {
                counts.dependency++;
                continue;
            }
            if ((flags & 64u) != 0 &&
                !quorum_dependency_ok(stations, station, seq, sensor, timestamp)) {
                counts.dependency++;
                continue;
            }
            uint16_t old_key = k->data_key;
            k->has_data_seq = 1;
            k->data_seq = seq;
            k->active = 0;
            k->timestamp = timestamp;
            k->data_key = delete_data_key(old_key, seq, timestamp);
            counts.accepted++;
        }
    }

    fclose(f);

    long long rejected = counts.bad_length + counts.bad_magic + counts.bad_crc +
                         counts.bad_version + counts.bad_flags + counts.bad_type +
                         counts.bad_layout + counts.stale + counts.dependency;
    printf("summary accepted=%lld rejected=%lld\n", counts.accepted, rejected);
    printf("reject bad_length=%lld\n", counts.bad_length);
    printf("reject bad_magic=%lld\n", counts.bad_magic);
    printf("reject bad_crc=%lld\n", counts.bad_crc);
    printf("reject bad_version=%lld\n", counts.bad_version);
    printf("reject bad_flags=%lld\n", counts.bad_flags);
    printf("reject bad_type=%lld\n", counts.bad_type);
    printf("reject bad_layout=%lld\n", counts.bad_layout);
    printf("reject stale=%lld\n", counts.stale);
    printf("reject dependency=%lld\n", counts.dependency);

    KeyState *active[MAX_KEYS];
    size_t nactive = 0;
    for (size_t i = 0; i < nkeys; i++) {
        if (keys[i].used && keys[i].active) {
            active[nactive++] = &keys[i];
        }
    }
    qsort(active, nactive, sizeof(active[0]), active_cmp);

    for (size_t i = 0; i < nactive; i++) {
        KeyState *k = active[i];
        int64_t calibrated = ((int64_t)k->raw * (int64_t)k->scale_ppm) / 1000 +
                             (int64_t)k->offset_milli;
        printf("sensor station=%u sensor=%u seq=%u time=%lld raw=%d calibrated_milli=%lld\n",
               (unsigned)k->station, (unsigned)k->sensor, (unsigned)k->data_seq,
               (long long)k->timestamp, k->raw, (long long)calibrated);
    }

    return 0;
}
