#define _POSIX_C_SOURCE 200809L

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <jansson.h>
#include <limits.h>
#include <math.h>
#include <openssl/evp.h>
#include <sqlite3.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <yaml.h>

#define ARRAY_GROW 8
#define ID_MAX 64

typedef struct {
    char *level_id;
    char *experiment_name;
    char *start_room;
    char *goal_room;
    char *directions[4];
    json_t *rooms;
    json_t *puzzles;
} Config;

typedef struct {
    char *run_id;
    char *kind;
    char *target;
    char *parent_id;
    char digest[65];
    int revision;
    sqlite3_int64 commit_ts;
    json_t *patch;
    int parent_index;
} Run;

typedef struct {
    char *kind;
    char *target;
    int *choices;
    size_t choice_count;
    size_t choice_cap;
} Group;

typedef struct {
    Run *runs;
    size_t run_count;
    size_t run_cap;
    Group *groups;
    size_t group_count;
    sqlite3_int64 experiment_id;
} Store;

typedef struct {
    const Config *config;
    const Store *store;
    int *current;
    int *best;
    bool found;
    int64_t best_revision_sum;
    long double best_timestamp_sum;
    json_t *best_rooms;
    json_t *best_puzzles;
} Search;

typedef struct {
    char **items;
    size_t count;
    size_t cap;
} StringList;

static void free_config(Config *cfg);
static void free_store(Store *store);

static char *xstrdup(const char *value) {
    char *copy = strdup(value == NULL ? "" : value);
    if (copy == NULL) {
        fputs("out of memory\n", stderr);
        exit(70);
    }
    return copy;
}

static void *xrealloc(void *ptr, size_t size) {
    void *next = realloc(ptr, size);
    if (next == NULL) {
        fputs("out of memory\n", stderr);
        exit(70);
    }
    return next;
}

static bool absolute_path(const char *path) {
    return path != NULL && path[0] == '/';
}

static bool valid_id(const char *value) {
    size_t length;
    if (value == NULL) {
        return false;
    }
    length = strlen(value);
    if (length == 0 || length > ID_MAX || !isalnum((unsigned char)value[0])) {
        return false;
    }
    for (size_t i = 1; i < length; ++i) {
        unsigned char c = (unsigned char)value[i];
        if (!isalnum(c) && c != '.' && c != '_' && c != '-') {
            return false;
        }
    }
    return true;
}

static bool valid_sha(const char *value) {
    if (value == NULL || strlen(value) != 64) {
        return false;
    }
    for (size_t i = 0; i < 64; ++i) {
        if (!isdigit((unsigned char)value[i]) &&
            !(value[i] >= 'a' && value[i] <= 'f')) {
            return false;
        }
    }
    return true;
}

static int strict_revision(const char *text, int *output) {
    char *end = NULL;
    long value;
    if (text == NULL || text[0] == '\0') {
        return -1;
    }
    for (const char *p = text; *p != '\0'; ++p) {
        if (!isdigit((unsigned char)*p)) {
            return -1;
        }
    }
    errno = 0;
    value = strtol(text, &end, 10);
    if (errno != 0 || end == NULL || *end != '\0' || value < 1 ||
        value > INT_MAX) {
        return -1;
    }
    *output = (int)value;
    return 0;
}

static int read_file(const char *path, unsigned char **output, size_t *size) {
    FILE *stream = fopen(path, "rb");
    unsigned char *data = NULL;
    long length;
    if (stream == NULL) {
        return -1;
    }
    if (fseek(stream, 0, SEEK_END) != 0 || (length = ftell(stream)) < 0 ||
        fseek(stream, 0, SEEK_SET) != 0) {
        fclose(stream);
        return -1;
    }
    data = malloc((size_t)length + 1);
    if (data == NULL) {
        fclose(stream);
        return -1;
    }
    if ((size_t)length != fread(data, 1, (size_t)length, stream) ||
        ferror(stream)) {
        free(data);
        fclose(stream);
        return -1;
    }
    data[length] = '\0';
    fclose(stream);
    *output = data;
    *size = (size_t)length;
    return 0;
}

static int sha256_bytes(const void *data, size_t size, char output[65]) {
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int digest_size = 0;
    static const char hex[] = "0123456789abcdef";
    if (ctx == NULL || EVP_DigestInit_ex(ctx, EVP_sha256(), NULL) != 1 ||
        EVP_DigestUpdate(ctx, data, size) != 1 ||
        EVP_DigestFinal_ex(ctx, digest, &digest_size) != 1 ||
        digest_size != 32) {
        EVP_MD_CTX_free(ctx);
        return -1;
    }
    EVP_MD_CTX_free(ctx);
    for (size_t i = 0; i < 32; ++i) {
        output[i * 2] = hex[digest[i] >> 4];
        output[i * 2 + 1] = hex[digest[i] & 15];
    }
    output[64] = '\0';
    return 0;
}

static int sha256_file(const char *path, char output[65]) {
    unsigned char *data = NULL;
    size_t size = 0;
    int result;
    if (read_file(path, &data, &size) != 0) {
        return -1;
    }
    result = sha256_bytes(data, size, output);
    free(data);
    return result;
}

static int atomic_write(const char *path, const void *data, size_t size) {
    char *temporary;
    size_t temporary_size = strlen(path) + 64;
    int fd = -1;
    size_t offset = 0;
    int result = -1;
    temporary = malloc(temporary_size);
    if (temporary == NULL) {
        return -1;
    }
    snprintf(temporary, temporary_size, "%s.tmp.%ld", path, (long)getpid());
    fd = open(temporary, O_WRONLY | O_CREAT | O_EXCL, 0600);
    if (fd < 0) {
        free(temporary);
        return -1;
    }
    while (offset < size) {
        ssize_t written = write(fd, (const unsigned char *)data + offset,
                                size - offset);
        if (written < 0) {
            if (errno == EINTR) {
                continue;
            }
            goto done;
        }
        offset += (size_t)written;
    }
    if (fsync(fd) != 0 || close(fd) != 0) {
        fd = -1;
        goto done;
    }
    fd = -1;
    if (rename(temporary, path) != 0) {
        goto done;
    }
    result = 0;
done:
    if (fd >= 0) {
        close(fd);
    }
    if (result != 0) {
        unlink(temporary);
    }
    free(temporary);
    return result;
}

static yaml_node_t *mapping_value(yaml_document_t *doc, yaml_node_t *mapping,
                                  const char *key) {
    yaml_node_pair_t *pair;
    if (mapping == NULL || mapping->type != YAML_MAPPING_NODE) {
        return NULL;
    }
    for (pair = mapping->data.mapping.pairs.start;
         pair < mapping->data.mapping.pairs.top; ++pair) {
        yaml_node_t *key_node = yaml_document_get_node(doc, pair->key);
        if (key_node != NULL && key_node->type == YAML_SCALAR_NODE &&
            strcmp((const char *)key_node->data.scalar.value, key) == 0) {
            return yaml_document_get_node(doc, pair->value);
        }
    }
    return NULL;
}

static const char *yaml_scalar(yaml_node_t *node) {
    if (node == NULL || node->type != YAML_SCALAR_NODE) {
        return NULL;
    }
    return (const char *)node->data.scalar.value;
}

static bool yaml_null(yaml_node_t *node) {
    const char *value;
    if (node == NULL || node->type != YAML_SCALAR_NODE) {
        return false;
    }
    value = (const char *)node->data.scalar.value;
    return strcmp(value, "null") == 0 || strcmp(value, "Null") == 0 ||
           strcmp(value, "NULL") == 0 || strcmp(value, "~") == 0 ||
           node->data.scalar.length == 0;
}

static bool direction_name(const char *value) {
    return value != NULL &&
           (strcmp(value, "north") == 0 || strcmp(value, "east") == 0 ||
            strcmp(value, "south") == 0 || strcmp(value, "west") == 0);
}

static int load_yaml(const char *path, Config *cfg) {
    FILE *stream = NULL;
    yaml_parser_t parser;
    yaml_document_t doc;
    yaml_node_t *root;
    yaml_node_t *node;
    bool parser_ready = false;
    bool doc_ready = false;
    int result = -1;
    const char *value;

    stream = fopen(path, "rb");
    if (stream == NULL || !yaml_parser_initialize(&parser)) {
        if (stream != NULL) fclose(stream);
        return -1;
    }
    parser_ready = true;
    yaml_parser_set_input_file(&parser, stream);
    if (!yaml_parser_load(&parser, &doc)) {
        goto done;
    }
    doc_ready = true;
    root = yaml_document_get_root_node(&doc);
    if (root == NULL || root->type != YAML_MAPPING_NODE) {
        goto done;
    }
    value = yaml_scalar(mapping_value(&doc, root, "format"));
    if (value == NULL || strcmp(value, "mlflow-maze-board-v1") != 0) {
        goto done;
    }
    value = yaml_scalar(mapping_value(&doc, root, "level_id"));
    if (!valid_id(value)) goto done;
    cfg->level_id = xstrdup(value);
    value = yaml_scalar(mapping_value(&doc, root, "experiment_name"));
    if (value == NULL || value[0] == '\0') goto done;
    cfg->experiment_name = xstrdup(value);
    value = yaml_scalar(mapping_value(&doc, root, "start_room"));
    if (!valid_id(value)) goto done;
    cfg->start_room = xstrdup(value);
    value = yaml_scalar(mapping_value(&doc, root, "goal_room"));
    if (!valid_id(value)) goto done;
    cfg->goal_room = xstrdup(value);

    node = mapping_value(&doc, root, "direction_order");
    if (node == NULL || node->type != YAML_SEQUENCE_NODE ||
        node->data.sequence.items.top - node->data.sequence.items.start != 4) {
        goto done;
    }
    for (int i = 0; i < 4; ++i) {
        yaml_node_t *item = yaml_document_get_node(
            &doc, node->data.sequence.items.start[i]);
        value = yaml_scalar(item);
        if (!direction_name(value)) goto done;
        for (int j = 0; j < i; ++j) {
            if (strcmp(cfg->directions[j], value) == 0) goto done;
        }
        cfg->directions[i] = xstrdup(value);
    }

    cfg->rooms = json_object();
    if (cfg->rooms == NULL) goto done;
    node = mapping_value(&doc, root, "rooms");
    if (node == NULL || node->type != YAML_SEQUENCE_NODE) goto done;
    for (yaml_node_item_t *item = node->data.sequence.items.start;
         item < node->data.sequence.items.top; ++item) {
        yaml_node_t *room_node = yaml_document_get_node(&doc, *item);
        yaml_node_t *field;
        json_t *room = NULL;
        json_t *exits = NULL;
        const char *id;
        if (room_node == NULL || room_node->type != YAML_MAPPING_NODE) goto done;
        id = yaml_scalar(mapping_value(&doc, room_node, "id"));
        if (!valid_id(id) || json_object_get(cfg->rooms, id) != NULL) goto done;
        room = json_object();
        exits = json_object();
        if (room == NULL || exits == NULL) {
            json_decref(room);
            json_decref(exits);
            goto done;
        }
        json_object_set_new(room, "id", json_string(id));
        field = mapping_value(&doc, room_node, "title");
        if (field == NULL || yaml_null(field)) {
            json_object_set_new(room, "title", json_null());
        } else if ((value = yaml_scalar(field)) != NULL) {
            json_object_set_new(room, "title", json_string(value));
        } else {
            json_decref(room); json_decref(exits); goto done;
        }
        field = mapping_value(&doc, room_node, "prompt_id");
        if (field == NULL || yaml_null(field)) {
            json_object_set_new(room, "prompt_id", json_null());
        } else if ((value = yaml_scalar(field)) != NULL && valid_id(value)) {
            json_object_set_new(room, "prompt_id", json_string(value));
        } else {
            json_decref(room); json_decref(exits); goto done;
        }
        field = mapping_value(&doc, room_node, "exits");
        if (field != NULL) {
            if (field->type != YAML_MAPPING_NODE) {
                json_decref(room); json_decref(exits); goto done;
            }
            for (yaml_node_pair_t *pair = field->data.mapping.pairs.start;
                 pair < field->data.mapping.pairs.top; ++pair) {
                yaml_node_t *k = yaml_document_get_node(&doc, pair->key);
                yaml_node_t *v = yaml_document_get_node(&doc, pair->value);
                const char *direction = yaml_scalar(k);
                if (!direction_name(direction) || json_object_get(exits, direction)) {
                    json_decref(room); json_decref(exits); goto done;
                }
                if (!yaml_null(v)) {
                    const char *target = yaml_scalar(v);
                    if (!valid_id(target)) {
                        json_decref(room); json_decref(exits); goto done;
                    }
                    json_object_set_new(exits, direction, json_string(target));
                }
            }
        }
        json_object_set_new(room, "exits", exits);
        json_object_set_new(room, "_revision", json_integer(0));
        json_object_set_new(room, "_run_id", json_null());
        json_object_set_new(cfg->rooms, id, room);
    }
    result = json_object_size(cfg->rooms) > 0 ? 0 : -1;
done:
    if (doc_ready) yaml_document_delete(&doc);
    if (parser_ready) yaml_parser_delete(&parser);
    if (stream != NULL) fclose(stream);
    return result;
}

static char *trim(char *text) {
    char *end;
    while (isspace((unsigned char)*text)) ++text;
    end = text + strlen(text);
    while (end > text && isspace((unsigned char)end[-1])) --end;
    *end = '\0';
    return text;
}

static void strip_toml_comment(char *line) {
    bool quoted = false;
    bool escaped = false;
    for (char *p = line; *p != '\0'; ++p) {
        if (quoted && escaped) {
            escaped = false;
        } else if (quoted && *p == '\\') {
            escaped = true;
        } else if (*p == '"') {
            quoted = !quoted;
        } else if (!quoted && *p == '#') {
            *p = '\0';
            return;
        }
    }
}

static char *parse_toml_string(const char *text) {
    size_t length = strlen(text);
    char *output;
    size_t used = 0;
    if (length < 2 || text[0] != '"' || text[length - 1] != '"') {
        return NULL;
    }
    output = malloc(length);
    if (output == NULL) return NULL;
    for (size_t i = 1; i + 1 < length; ++i) {
        char c = text[i];
        if (c == '\\') {
            if (++i + 1 >= length) { free(output); return NULL; }
            switch (text[i]) {
                case '"': c = '"'; break;
                case '\\': c = '\\'; break;
                case 'n': c = '\n'; break;
                case 'r': c = '\r'; break;
                case 't': c = '\t'; break;
                default: free(output); return NULL;
            }
        }
        output[used++] = c;
    }
    output[used] = '\0';
    return output;
}

static int load_toml(const char *path, Config *cfg) {
    FILE *stream = fopen(path, "rb");
    char *line = NULL;
    size_t cap = 0;
    ssize_t length;
    json_t *current = NULL;
    bool format_seen = false;
    int result = -1;
    if (stream == NULL) return -1;
    cfg->puzzles = json_object();
    if (cfg->puzzles == NULL) goto done;
    while ((length = getline(&line, &cap, stream)) >= 0) {
        char *text;
        (void)length;
        strip_toml_comment(line);
        text = trim(line);
        if (*text == '\0') continue;
        if (*text == '[') {
            size_t n = strlen(text);
            const char *prefix = "[puzzle.";
            char id[ID_MAX + 1];
            size_t id_len;
            if (n < strlen(prefix) + 2 || text[n - 1] != ']' ||
                strncmp(text, prefix, strlen(prefix)) != 0) goto done;
            id_len = n - strlen(prefix) - 1;
            if (id_len == 0 || id_len > ID_MAX) goto done;
            memcpy(id, text + strlen(prefix), id_len);
            id[id_len] = '\0';
            if (!valid_id(id) || json_object_get(cfg->puzzles, id)) goto done;
            current = json_object();
            if (current == NULL) goto done;
            json_object_set_new(current, "id", json_string(id));
            json_object_set_new(current, "_revision", json_integer(0));
            json_object_set_new(current, "_run_id", json_null());
            json_object_set_new(cfg->puzzles, id, current);
            continue;
        }
        char *equals = strchr(text, '=');
        char *key;
        char *raw;
        char *value;
        if (equals == NULL) goto done;
        *equals = '\0';
        key = trim(text);
        raw = trim(equals + 1);
        value = parse_toml_string(raw);
        if (value == NULL) goto done;
        if (current == NULL) {
            if (strcmp(key, "format") != 0 || format_seen ||
                strcmp(value, "mlflow-maze-puzzles-v1") != 0) {
                free(value); goto done;
            }
            format_seen = true;
        } else {
            if ((strcmp(key, "prompt") != 0 &&
                 strcmp(key, "answer_sha256") != 0) ||
                json_object_get(current, key) != NULL) {
                free(value); goto done;
            }
            json_object_set_new(current, key, json_string(value));
        }
        free(value);
    }
    if (ferror(stream) || !format_seen) goto done;
    result = 0;
done:
    free(line);
    fclose(stream);
    return result;
}

static int load_config(const char *yaml_path, const char *toml_path, Config *cfg) {
    memset(cfg, 0, sizeof(*cfg));
    if (load_yaml(yaml_path, cfg) != 0 || load_toml(toml_path, cfg) != 0) {
        free_config(cfg);
        return -1;
    }
    return 0;
}

static void free_config(Config *cfg) {
    if (cfg == NULL) return;
    free(cfg->level_id);
    free(cfg->experiment_name);
    free(cfg->start_room);
    free(cfg->goal_room);
    for (int i = 0; i < 4; ++i) free(cfg->directions[i]);
    json_decref(cfg->rooms);
    json_decref(cfg->puzzles);
    memset(cfg, 0, sizeof(*cfg));
}

static int fetch_text_values(sqlite3 *db, const char *table, const char *run_id,
                             const char *key, char ***values, size_t *count) {
    char sql[160];
    sqlite3_stmt *stmt = NULL;
    char **items = NULL;
    size_t used = 0;
    int rc;
    snprintf(sql, sizeof(sql),
             "SELECT value FROM %s WHERE run_uuid=?1 AND key=?2 ORDER BY rowid",
             table);
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK ||
        sqlite3_bind_text(stmt, 1, run_id, -1, SQLITE_TRANSIENT) != SQLITE_OK ||
        sqlite3_bind_text(stmt, 2, key, -1, SQLITE_TRANSIENT) != SQLITE_OK) {
        sqlite3_finalize(stmt);
        return -1;
    }
    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        const unsigned char *value = sqlite3_column_text(stmt, 0);
        if (value == NULL) {
            rc = SQLITE_ERROR;
            break;
        }
        items = xrealloc(items, (used + 1) * sizeof(*items));
        items[used++] = xstrdup((const char *)value);
    }
    if (rc != SQLITE_DONE) {
        for (size_t i = 0; i < used; ++i) free(items[i]);
        free(items);
        sqlite3_finalize(stmt);
        return -1;
    }
    sqlite3_finalize(stmt);
    *values = items;
    *count = used;
    return 0;
}

static void free_values(char **values, size_t count) {
    for (size_t i = 0; i < count; ++i) free(values[i]);
    free(values);
}

static int fetch_one(sqlite3 *db, const char *table, const char *run_id,
                     const char *key, bool required, char **value) {
    char **values = NULL;
    size_t count = 0;
    if (fetch_text_values(db, table, run_id, key, &values, &count) != 0 ||
        count > 1 || (required && count != 1)) {
        free_values(values, count);
        return -1;
    }
    *value = count == 1 ? xstrdup(values[0]) : NULL;
    free_values(values, count);
    return 0;
}

static int allowed_patch(const char *kind, json_t *patch) {
    const char *key;
    json_t *value;
    if (!json_is_object(patch)) return -1;
    json_object_foreach(patch, key, value) {
        if (strcmp(kind, "room") == 0) {
            if (strcmp(key, "title") != 0 && strcmp(key, "prompt_id") != 0 &&
                strcmp(key, "exits") != 0) return -1;
            if ((strcmp(key, "title") == 0 || strcmp(key, "prompt_id") == 0) &&
                !json_is_null(value) && !json_is_string(value)) return -1;
            if (strcmp(key, "prompt_id") == 0 && json_is_string(value) &&
                !valid_id(json_string_value(value))) return -1;
            if (strcmp(key, "exits") == 0) {
                const char *direction;
                json_t *target;
                if (!json_is_object(value)) return -1;
                json_object_foreach(value, direction, target) {
                    if (!direction_name(direction) ||
                        (!json_is_null(target) && !json_is_string(target)) ||
                        (json_is_string(target) &&
                         !valid_id(json_string_value(target)))) return -1;
                }
            }
        } else {
            if (strcmp(key, "prompt") != 0 &&
                strcmp(key, "answer_sha256") != 0) return -1;
            if (!json_is_null(value) && !json_is_string(value)) return -1;
        }
    }
    return 0;
}

static int load_patch(sqlite3 *db, Run *run) {
    sqlite3_stmt *stmt = NULL;
    const char *sql =
        "SELECT key,value FROM params WHERE run_uuid=?1 "
        "AND key LIKE 'maze.patch.%' ORDER BY key,rowid";
    char *joined = NULL;
    size_t used = 0;
    size_t capacity = 0;
    int expected = 0;
    int rc;
    char actual[65];
    json_error_t error;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK ||
        sqlite3_bind_text(stmt, 1, run->run_id, -1, SQLITE_TRANSIENT) != SQLITE_OK) {
        sqlite3_finalize(stmt);
        return -1;
    }
    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        const char *key = (const char *)sqlite3_column_text(stmt, 0);
        const char *value = (const char *)sqlite3_column_text(stmt, 1);
        const char *suffix;
        size_t length;
        int index;
        if (key == NULL || value == NULL || strlen(key) != 14 ||
            strncmp(key, "maze.patch.", 11) != 0) {
            rc = SQLITE_ERROR;
            break;
        }
        suffix = key + 11;
        if (!isdigit((unsigned char)suffix[0]) ||
            !isdigit((unsigned char)suffix[1]) ||
            !isdigit((unsigned char)suffix[2]) || suffix[3] != '\0') {
            rc = SQLITE_ERROR;
            break;
        }
        index = (suffix[0] - '0') * 100 + (suffix[1] - '0') * 10 +
                suffix[2] - '0';
        if (index != expected++) {
            rc = SQLITE_ERROR;
            break;
        }
        length = strlen(value);
        if (used + length + 1 > capacity) {
            capacity = (used + length + 1) * 2;
            joined = xrealloc(joined, capacity);
        }
        memcpy(joined + used, value, length);
        used += length;
    }
    if (rc != SQLITE_DONE || expected == 0) {
        free(joined);
        sqlite3_finalize(stmt);
        return -1;
    }
    sqlite3_finalize(stmt);
    joined[used] = '\0';
    if (sha256_bytes(joined, used, actual) != 0 ||
        strcmp(actual, run->digest) != 0) {
        free(joined);
        return -1;
    }
    run->patch = json_loadb(joined, used, JSON_REJECT_DUPLICATES, &error);
    free(joined);
    if (run->patch == NULL || allowed_patch(run->kind, run->patch) != 0) {
        json_decref(run->patch);
        run->patch = NULL;
        return -1;
    }
    return 0;
}

static int load_commit(sqlite3 *db, Run *run) {
    sqlite3_stmt *stmt = NULL;
    const char *sql =
        "SELECT value,timestamp,step FROM metrics WHERE run_uuid=?1 "
        "AND key='maze.commit' ORDER BY timestamp DESC,rowid DESC LIMIT 1";
    int rc;
    double value;
    sqlite3_int64 step;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK ||
        sqlite3_bind_text(stmt, 1, run->run_id, -1, SQLITE_TRANSIENT) != SQLITE_OK) {
        sqlite3_finalize(stmt);
        return -1;
    }
    rc = sqlite3_step(stmt);
    if (rc != SQLITE_ROW) {
        sqlite3_finalize(stmt);
        return -1;
    }
    value = sqlite3_column_double(stmt, 0);
    run->commit_ts = sqlite3_column_int64(stmt, 1);
    step = sqlite3_column_int64(stmt, 2);
    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    if (rc != SQLITE_DONE || !isfinite(value) || value != 1.0 ||
        step != run->revision) return -1;
    return 0;
}

static int append_run(Store *store, Run *run) {
    if (store->run_count == store->run_cap) {
        store->run_cap = store->run_cap == 0 ? ARRAY_GROW : store->run_cap * 2;
        store->runs = xrealloc(store->runs, store->run_cap * sizeof(*store->runs));
    }
    store->runs[store->run_count++] = *run;
    memset(run, 0, sizeof(*run));
    return 0;
}

static int run_index(const Store *store, const char *run_id) {
    for (size_t i = 0; i < store->run_count; ++i) {
        if (strcmp(store->runs[i].run_id, run_id) == 0) return (int)i;
    }
    return -1;
}

static int group_compare(const void *left, const void *right) {
    const Group *a = left;
    const Group *b = right;
    int value = strcmp(a->kind, b->kind);
    return value != 0 ? value : strcmp(a->target, b->target);
}

static int choice_compare_ctx(const Store *store, int a, int b) {
    const Run *ra;
    const Run *rb;
    if (a < 0) return b < 0 ? 0 : 1;
    if (b < 0) return -1;
    ra = &store->runs[a];
    rb = &store->runs[b];
    if (ra->revision != rb->revision) return ra->revision > rb->revision ? -1 : 1;
    if (ra->commit_ts != rb->commit_ts) return ra->commit_ts > rb->commit_ts ? -1 : 1;
    return strcmp(ra->run_id, rb->run_id);
}

static void sort_group_choices(Store *store, Group *group) {
    for (size_t i = 1; i < group->choice_count; ++i) {
        int value = group->choices[i];
        size_t j = i;
        while (j > 0 && choice_compare_ctx(store, value, group->choices[j - 1]) < 0) {
            group->choices[j] = group->choices[j - 1];
            --j;
        }
        group->choices[j] = value;
    }
}

static int build_groups(Store *store) {
    for (size_t i = 0; i < store->run_count; ++i) {
        Run *run = &store->runs[i];
        Group *group = NULL;
        for (size_t j = 0; j < store->group_count; ++j) {
            if (strcmp(store->groups[j].kind, run->kind) == 0 &&
                strcmp(store->groups[j].target, run->target) == 0) {
                group = &store->groups[j];
                break;
            }
        }
        if (group == NULL) {
            store->groups = xrealloc(store->groups,
                                     (store->group_count + 1) * sizeof(*store->groups));
            group = &store->groups[store->group_count++];
            memset(group, 0, sizeof(*group));
            group->kind = xstrdup(run->kind);
            group->target = xstrdup(run->target);
            group->choice_cap = ARRAY_GROW;
            group->choices = xrealloc(NULL, group->choice_cap * sizeof(int));
            group->choices[group->choice_count++] = -1;
        }
        if (group->choice_count == group->choice_cap) {
            group->choice_cap *= 2;
            group->choices = xrealloc(group->choices,
                                      group->choice_cap * sizeof(int));
        }
        group->choices[group->choice_count++] = (int)i;
    }
    qsort(store->groups, store->group_count, sizeof(*store->groups), group_compare);
    for (size_t i = 0; i < store->group_count; ++i) {
        sort_group_choices(store, &store->groups[i]);
    }
    return 0;
}

static int load_store(const char *path, const Config *cfg, Store *store) {
    sqlite3 *db = NULL;
    sqlite3_stmt *stmt = NULL;
    int rc;
    int matches = 0;
    memset(store, 0, sizeof(*store));
    if (sqlite3_open_v2(path, &db, SQLITE_OPEN_READONLY, NULL) != SQLITE_OK) {
        sqlite3_close(db);
        return -1;
    }
    sqlite3_busy_timeout(db, 2000);
    if (sqlite3_prepare_v2(db,
            "SELECT experiment_id FROM experiments WHERE name=?1 "
            "AND lifecycle_stage='active' ORDER BY experiment_id", -1,
            &stmt, NULL) != SQLITE_OK ||
        sqlite3_bind_text(stmt, 1, cfg->experiment_name, -1, SQLITE_TRANSIENT) != SQLITE_OK) {
        goto fail;
    }
    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        store->experiment_id = sqlite3_column_int64(stmt, 0);
        ++matches;
    }
    if (rc != SQLITE_DONE || matches != 1) goto fail;
    sqlite3_finalize(stmt);
    stmt = NULL;

    if (sqlite3_prepare_v2(db,
            "SELECT run_uuid FROM runs WHERE experiment_id=?1 "
            "AND status='FINISHED' AND lifecycle_stage='active' ORDER BY run_uuid",
            -1, &stmt, NULL) != SQLITE_OK ||
        sqlite3_bind_int64(stmt, 1, store->experiment_id) != SQLITE_OK) goto fail;
    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        const char *run_id = (const char *)sqlite3_column_text(stmt, 0);
        char **levels = NULL;
        size_t level_count = 0;
        bool matching = false;
        Run run;
        char *revision = NULL;
        memset(&run, 0, sizeof(run));
        run.parent_index = -1;
        if (run_id == NULL || fetch_text_values(db, "tags", run_id,
                                                "maze.level_id", &levels,
                                                &level_count) != 0) goto fail;
        for (size_t i = 0; i < level_count; ++i) {
            if (strcmp(levels[i], cfg->level_id) == 0) matching = true;
        }
        if (!matching) {
            free_values(levels, level_count);
            continue;
        }
        if (level_count != 1) {
            free_values(levels, level_count);
            goto fail;
        }
        free_values(levels, level_count);
        run.run_id = xstrdup(run_id);
        if (fetch_one(db, "tags", run_id, "maze.record_kind", true,
                      &run.kind) != 0 ||
            fetch_one(db, "tags", run_id, "maze.target_id", true,
                      &run.target) != 0 ||
            fetch_one(db, "tags", run_id, "maze.patch_sha256", true,
                      &revision) != 0) {
            free(run.run_id); free(run.kind); free(run.target); free(revision);
            goto fail;
        }
        if ((strcmp(run.kind, "room") != 0 && strcmp(run.kind, "puzzle") != 0) ||
            !valid_id(run.target) || !valid_sha(revision)) {
            free(run.run_id); free(run.kind); free(run.target); free(revision);
            goto fail;
        }
        memcpy(run.digest, revision, 65);
        free(revision);
        revision = NULL;
        if (fetch_one(db, "tags", run_id, "maze.parent_run_id", false,
                      &run.parent_id) != 0 ||
            fetch_one(db, "params", run_id, "maze.revision", true,
                      &revision) != 0 ||
            strict_revision(revision, &run.revision) != 0 ||
            load_patch(db, &run) != 0 || load_commit(db, &run) != 0) {
            free(run.run_id); free(run.kind); free(run.target);
            free(run.parent_id); free(revision); json_decref(run.patch);
            goto fail;
        }
        free(revision);
        append_run(store, &run);
    }
    if (rc != SQLITE_DONE) goto fail;
    sqlite3_finalize(stmt);
    stmt = NULL;

    for (size_t i = 0; i < store->run_count; ++i) {
        Run *run = &store->runs[i];
        if (run->revision == 1) {
            if (run->parent_id != NULL) goto fail;
        } else {
            if (run->parent_id == NULL ||
                (run->parent_index = run_index(store, run->parent_id)) < 0) goto fail;
            Run *parent = &store->runs[run->parent_index];
            if (strcmp(parent->kind, run->kind) != 0 ||
                strcmp(parent->target, run->target) != 0 ||
                parent->revision != run->revision - 1) goto fail;
        }
    }
    build_groups(store);
    sqlite3_close(db);
    return 0;
fail:
    sqlite3_finalize(stmt);
    sqlite3_close(db);
    free_store(store);
    return -1;
}

static void free_store(Store *store) {
    if (store == NULL) return;
    for (size_t i = 0; i < store->run_count; ++i) {
        free(store->runs[i].run_id);
        free(store->runs[i].kind);
        free(store->runs[i].target);
        free(store->runs[i].parent_id);
        json_decref(store->runs[i].patch);
    }
    for (size_t i = 0; i < store->group_count; ++i) {
        free(store->groups[i].kind);
        free(store->groups[i].target);
        free(store->groups[i].choices);
    }
    free(store->runs);
    free(store->groups);
    memset(store, 0, sizeof(*store));
}

static int merge_patch(json_t *target, json_t *patch) {
    const char *key;
    json_t *value;
    json_object_foreach(patch, key, value) {
        if (json_is_null(value)) {
            json_object_del(target, key);
        } else if (json_is_object(value)) {
            json_t *current = json_object_get(target, key);
            if (!json_is_object(current)) {
                current = json_object();
                if (current == NULL || json_object_set_new(target, key, current) != 0)
                    return -1;
            }
            if (merge_patch(current, value) != 0) return -1;
        } else if (json_object_set(target, key, value) != 0) {
            return -1;
        }
    }
    return 0;
}

static int string_compare(const void *left, const void *right) {
    const char *const *a = left;
    const char *const *b = right;
    return strcmp(*a, *b);
}

static int object_keys(json_t *object, StringList *list) {
    const char *key;
    json_t *value;
    memset(list, 0, sizeof(*list));
    json_object_foreach(object, key, value) {
        (void)value;
        if (list->count == list->cap) {
            list->cap = list->cap == 0 ? ARRAY_GROW : list->cap * 2;
            list->items = xrealloc(list->items, list->cap * sizeof(*list->items));
        }
        list->items[list->count++] = xstrdup(key);
    }
    qsort(list->items, list->count, sizeof(*list->items), string_compare);
    return 0;
}

static void string_list_free(StringList *list) {
    for (size_t i = 0; i < list->count; ++i) free(list->items[i]);
    free(list->items);
    memset(list, 0, sizeof(*list));
}

static int direction_index(const Config *cfg, const char *direction) {
    for (int i = 0; i < 4; ++i) {
        if (strcmp(cfg->directions[i], direction) == 0) return i;
    }
    return -1;
}

static bool can_reach(const Config *cfg, json_t *rooms, const char *start,
                      const char *goal) {
    StringList ids;
    bool *seen = NULL;
    size_t *queue = NULL;
    size_t head = 0;
    size_t tail = 0;
    int start_index = -1;
    int goal_index = -1;
    bool result = false;
    object_keys(rooms, &ids);
    for (size_t i = 0; i < ids.count; ++i) {
        if (strcmp(ids.items[i], start) == 0) start_index = (int)i;
        if (strcmp(ids.items[i], goal) == 0) goal_index = (int)i;
    }
    if (start_index < 0 || goal_index < 0) goto done;
    seen = calloc(ids.count, sizeof(*seen));
    queue = malloc(ids.count * sizeof(*queue));
    if (seen == NULL || queue == NULL) goto done;
    seen[start_index] = true;
    queue[tail++] = (size_t)start_index;
    while (head < tail) {
        size_t index = queue[head++];
        json_t *room;
        json_t *exits;
        if ((int)index == goal_index) {
            result = true;
            break;
        }
        room = json_object_get(rooms, ids.items[index]);
        exits = json_object_get(room, "exits");
        for (int d = 0; d < 4; ++d) {
            json_t *target = json_object_get(exits, cfg->directions[d]);
            const char *target_id;
            if (!json_is_string(target)) continue;
            target_id = json_string_value(target);
            for (size_t next = 0; next < ids.count; ++next) {
                if (!seen[next] && strcmp(ids.items[next], target_id) == 0) {
                    seen[next] = true;
                    queue[tail++] = next;
                    break;
                }
            }
        }
    }
done:
    free(seen);
    free(queue);
    string_list_free(&ids);
    return result;
}

static bool validate_state(const Config *cfg, json_t *rooms, json_t *puzzles) {
    const char *id;
    json_t *room;
    StringList ids;
    bool ok = true;
    if (json_object_get(rooms, cfg->start_room) == NULL ||
        json_object_get(rooms, cfg->goal_room) == NULL) return false;
    json_object_foreach(rooms, id, room) {
        json_t *title = json_object_get(room, "title");
        json_t *prompt_id = json_object_get(room, "prompt_id");
        json_t *exits = json_object_get(room, "exits");
        const char *direction;
        json_t *target;
        if (!valid_id(id) || !json_is_string(title) ||
            json_string_length(title) == 0 || !json_is_object(exits)) return false;
        if (prompt_id != NULL && !json_is_null(prompt_id)) {
            json_t *puzzle;
            json_t *prompt;
            json_t *answer;
            const char *puzzle_id;
            if (!json_is_string(prompt_id)) return false;
            puzzle_id = json_string_value(prompt_id);
            puzzle = json_object_get(puzzles, puzzle_id);
            if (puzzle == NULL) return false;
            prompt = json_object_get(puzzle, "prompt");
            answer = json_object_get(puzzle, "answer_sha256");
            if (!json_is_string(prompt) || json_string_length(prompt) == 0 ||
                !json_is_string(answer) ||
                !valid_sha(json_string_value(answer))) return false;
        }
        json_object_foreach(exits, direction, target) {
            if (direction_index(cfg, direction) < 0 || !json_is_string(target) ||
                json_object_get(rooms, json_string_value(target)) == NULL) return false;
        }
    }
    object_keys(rooms, &ids);
    if (!can_reach(cfg, rooms, cfg->start_room, cfg->goal_room)) ok = false;
    for (size_t i = 0; ok && i < ids.count; ++i) {
        if (!can_reach(cfg, rooms, cfg->start_room, ids.items[i]) ||
            !can_reach(cfg, rooms, ids.items[i], cfg->goal_room)) ok = false;
    }
    string_list_free(&ids);
    return ok;
}

static json_t *new_entity(const char *kind, const char *target) {
    json_t *entity = json_object();
    if (entity == NULL) return NULL;
    json_object_set_new(entity, "id", json_string(target));
    if (strcmp(kind, "room") == 0) {
        json_object_set_new(entity, "title", json_null());
        json_object_set_new(entity, "prompt_id", json_null());
        json_object_set_new(entity, "exits", json_object());
    }
    json_object_set_new(entity, "_revision", json_integer(0));
    json_object_set_new(entity, "_run_id", json_null());
    return entity;
}

static int apply_tip(const Store *store, const Group *group, int tip,
                     json_t *rooms, json_t *puzzles) {
    int *chain = NULL;
    size_t count = 0;
    int current = tip;
    json_t *collection;
    json_t *entity;
    if (tip < 0) return 0;
    while (current >= 0) {
        chain = xrealloc(chain, (count + 1) * sizeof(*chain));
        chain[count++] = current;
        current = store->runs[current].parent_index;
    }
    collection = strcmp(group->kind, "room") == 0 ? rooms : puzzles;
    entity = json_object_get(collection, group->target);
    if (entity == NULL) {
        entity = new_entity(group->kind, group->target);
        if (entity == NULL || json_object_set_new(collection, group->target, entity) != 0) {
            json_decref(entity);
            free(chain);
            return -1;
        }
    }
    for (size_t i = count; i > 0; --i) {
        if (merge_patch(entity, store->runs[chain[i - 1]].patch) != 0) {
            free(chain);
            return -1;
        }
    }
    json_object_set_new(entity, "_revision",
                        json_integer(store->runs[tip].revision));
    json_object_set_new(entity, "_run_id",
                        json_string(store->runs[tip].run_id));
    free(chain);
    return 0;
}

static int selection_lex_compare(const Search *search, const int *left,
                                 const int *right) {
    for (size_t i = 0; i < search->store->group_count; ++i) {
        const char *a = left[i] < 0 ? "" : search->store->runs[left[i]].run_id;
        const char *b = right[i] < 0 ? "" : search->store->runs[right[i]].run_id;
        int value = strcmp(a, b);
        if (value != 0) return value;
    }
    return 0;
}

static void evaluate_selection(Search *search) {
    json_t *rooms = json_deep_copy(search->config->rooms);
    json_t *puzzles = json_deep_copy(search->config->puzzles);
    int64_t revision_sum = 0;
    long double timestamp_sum = 0.0L;
    bool better;
    if (rooms == NULL || puzzles == NULL) goto done;
    for (size_t i = 0; i < search->store->group_count; ++i) {
        int tip = search->current[i];
        if (apply_tip(search->store, &search->store->groups[i], tip,
                      rooms, puzzles) != 0) goto done;
        if (tip >= 0) {
            revision_sum += search->store->runs[tip].revision;
            timestamp_sum += (long double)search->store->runs[tip].commit_ts;
        }
    }
    if (!validate_state(search->config, rooms, puzzles)) goto done;
    better = !search->found || revision_sum > search->best_revision_sum ||
             (revision_sum == search->best_revision_sum &&
              timestamp_sum > search->best_timestamp_sum) ||
             (revision_sum == search->best_revision_sum &&
              timestamp_sum == search->best_timestamp_sum &&
              selection_lex_compare(search, search->current, search->best) < 0);
    if (better) {
        memcpy(search->best, search->current,
               search->store->group_count * sizeof(*search->best));
        search->best_revision_sum = revision_sum;
        search->best_timestamp_sum = timestamp_sum;
        search->found = true;
        json_decref(search->best_rooms);
        json_decref(search->best_puzzles);
        search->best_rooms = rooms;
        search->best_puzzles = puzzles;
        rooms = NULL;
        puzzles = NULL;
    }
done:
    json_decref(rooms);
    json_decref(puzzles);
}

static void search_choices(Search *search, size_t group_index) {
    const Group *group;
    if (group_index == search->store->group_count) {
        evaluate_selection(search);
        return;
    }
    group = &search->store->groups[group_index];
    for (size_t i = 0; i < group->choice_count; ++i) {
        search->current[group_index] = group->choices[i];
        search_choices(search, group_index + 1);
    }
}

static int select_level(const Config *cfg, const Store *store, Search *search) {
    memset(search, 0, sizeof(*search));
    search->config = cfg;
    search->store = store;
    search->current = calloc(store->group_count == 0 ? 1 : store->group_count,
                             sizeof(*search->current));
    search->best = calloc(store->group_count == 0 ? 1 : store->group_count,
                          sizeof(*search->best));
    if (search->current == NULL || search->best == NULL) return -1;
    search_choices(search, 0);
    return search->found ? 0 : -1;
}

static void free_search(Search *search) {
    free(search->current);
    free(search->best);
    json_decref(search->best_rooms);
    json_decref(search->best_puzzles);
    memset(search, 0, sizeof(*search));
}

static int list_add_format(StringList *list, const char *format, ...) {
    va_list arguments;
    va_list copy;
    int length;
    char *text;
    va_start(arguments, format);
    va_copy(copy, arguments);
    length = vsnprintf(NULL, 0, format, copy);
    va_end(copy);
    if (length < 0) {
        va_end(arguments);
        return -1;
    }
    text = malloc((size_t)length + 1);
    if (text == NULL) {
        va_end(arguments);
        return -1;
    }
    vsnprintf(text, (size_t)length + 1, format, arguments);
    va_end(arguments);
    if (list->count == list->cap) {
        list->cap = list->cap == 0 ? ARRAY_GROW : list->cap * 2;
        list->items = xrealloc(list->items, list->cap * sizeof(*list->items));
    }
    list->items[list->count++] = text;
    return 0;
}

static int build_walkthrough(const Config *cfg, json_t *rooms, json_t *puzzles,
                             json_t **output) {
    StringList ids;
    int start = -1;
    int goal = -1;
    int *parent = NULL;
    int *parent_direction = NULL;
    size_t *queue = NULL;
    size_t head = 0;
    size_t tail = 0;
    int *path = NULL;
    size_t path_count = 0;
    StringList lines = {0};
    json_t *walk = NULL;
    json_t *moves = NULL;
    json_t *path_rooms = NULL;
    json_t *transcript = NULL;
    char digest[65];
    char *digest_input = NULL;
    size_t digest_size = 0;
    int result = -1;

    object_keys(rooms, &ids);
    for (size_t i = 0; i < ids.count; ++i) {
        if (strcmp(ids.items[i], cfg->start_room) == 0) start = (int)i;
        if (strcmp(ids.items[i], cfg->goal_room) == 0) goal = (int)i;
    }
    if (start < 0 || goal < 0) goto done;
    parent = malloc(ids.count * sizeof(*parent));
    parent_direction = malloc(ids.count * sizeof(*parent_direction));
    queue = malloc(ids.count * sizeof(*queue));
    if (parent == NULL || parent_direction == NULL || queue == NULL) goto done;
    for (size_t i = 0; i < ids.count; ++i) {
        parent[i] = -2;
        parent_direction[i] = -1;
    }
    parent[start] = -1;
    queue[tail++] = (size_t)start;
    while (head < tail && parent[goal] == -2) {
        size_t current = queue[head++];
        json_t *room = json_object_get(rooms, ids.items[current]);
        json_t *exits = json_object_get(room, "exits");
        for (int d = 0; d < 4; ++d) {
            json_t *target = json_object_get(exits, cfg->directions[d]);
            if (!json_is_string(target)) continue;
            for (size_t next = 0; next < ids.count; ++next) {
                if (parent[next] == -2 &&
                    strcmp(ids.items[next], json_string_value(target)) == 0) {
                    parent[next] = (int)current;
                    parent_direction[next] = d;
                    queue[tail++] = next;
                    break;
                }
            }
        }
    }
    if (parent[goal] == -2) goto done;
    for (int current = goal; current >= 0; current = parent[current]) {
        path = xrealloc(path, (path_count + 1) * sizeof(*path));
        path[path_count++] = current;
    }
    for (size_t i = 0; i < path_count / 2; ++i) {
        int swap = path[i];
        path[i] = path[path_count - 1 - i];
        path[path_count - 1 - i] = swap;
    }

    walk = json_object();
    moves = json_array();
    path_rooms = json_array();
    transcript = json_array();
    if (walk == NULL || moves == NULL || path_rooms == NULL || transcript == NULL)
        goto done;
    for (size_t i = 0; i < path_count; ++i) {
        json_t *room = json_object_get(rooms, ids.items[path[i]]);
        json_t *prompt_id = json_object_get(room, "prompt_id");
        json_array_append_new(path_rooms, json_string(ids.items[path[i]]));
        if (i == 0) {
            list_add_format(&lines, "enter 0 %s", ids.items[path[i]]);
        } else {
            int direction = parent_direction[path[i]];
            json_array_append_new(moves, json_string(cfg->directions[direction]));
            list_add_format(&lines, "move %zu %s %s %s", i,
                            cfg->directions[direction], ids.items[path[i - 1]],
                            ids.items[path[i]]);
            list_add_format(&lines, "enter %zu %s", i, ids.items[path[i]]);
        }
        if (json_is_string(prompt_id)) {
            const char *puzzle_id = json_string_value(prompt_id);
            json_t *puzzle = json_object_get(puzzles, puzzle_id);
            json_t *answer = json_object_get(puzzle, "answer_sha256");
            list_add_format(&lines, "prompt %zu %s %s", i, puzzle_id,
                            json_string_value(answer));
        }
    }
    list_add_format(&lines, "goal %zu %s", path_count - 1,
                    ids.items[path[path_count - 1]]);
    for (size_t i = 0; i < lines.count; ++i) {
        size_t n = strlen(lines.items[i]);
        digest_input = xrealloc(digest_input, digest_size + n + 1);
        memcpy(digest_input + digest_size, lines.items[i], n);
        digest_size += n;
        digest_input[digest_size++] = '\n';
        json_array_append_new(transcript, json_string(lines.items[i]));
    }
    if (sha256_bytes(digest_input, digest_size, digest) != 0) goto done;
    json_object_set_new(walk, "moves", moves); moves = NULL;
    json_object_set_new(walk, "rooms", path_rooms); path_rooms = NULL;
    json_object_set_new(walk, "sha256", json_string(digest));
    json_object_set_new(walk, "transcript", transcript); transcript = NULL;
    *output = walk;
    walk = NULL;
    result = 0;
done:
    free(parent);
    free(parent_direction);
    free(queue);
    free(path);
    free(digest_input);
    string_list_free(&lines);
    string_list_free(&ids);
    json_decref(walk);
    json_decref(moves);
    json_decref(path_rooms);
    json_decref(transcript);
    return result;
}

static json_t *manifest_rooms(const Config *cfg, json_t *rooms,
                              json_t *puzzles) {
    StringList ids;
    json_t *array = json_array();
    if (array == NULL) return NULL;
    object_keys(rooms, &ids);
    for (size_t i = 0; i < ids.count; ++i) {
        json_t *source = json_object_get(rooms, ids.items[i]);
        json_t *item = json_object();
        json_t *exits = json_array();
        json_t *prompt_output = json_null();
        json_t *prompt_id = json_object_get(source, "prompt_id");
        if (item == NULL || exits == NULL || prompt_output == NULL) {
            json_decref(item); json_decref(exits); json_decref(prompt_output);
            json_decref(array); array = NULL; break;
        }
        for (int d = 0; d < 4; ++d) {
            json_t *target = json_object_get(json_object_get(source, "exits"),
                                             cfg->directions[d]);
            if (json_is_string(target)) {
                json_t *edge = json_pack("{s:s,s:s}", "direction",
                                         cfg->directions[d], "to",
                                         json_string_value(target));
                json_array_append_new(exits, edge);
            }
        }
        if (json_is_string(prompt_id)) {
            const char *pid = json_string_value(prompt_id);
            json_t *puzzle = json_object_get(puzzles, pid);
            json_decref(prompt_output);
            prompt_output = json_object();
            json_object_set(prompt_output, "answer_sha256",
                            json_object_get(puzzle, "answer_sha256"));
            json_object_set_new(prompt_output, "id", json_string(pid));
            json_object_set(prompt_output, "prompt", json_object_get(puzzle, "prompt"));
            json_object_set(prompt_output, "revision",
                            json_object_get(puzzle, "_revision"));
            json_object_set(prompt_output, "run_id",
                            json_object_get(puzzle, "_run_id"));
        }
        json_object_set_new(item, "exits", exits);
        json_object_set_new(item, "id", json_string(ids.items[i]));
        json_object_set_new(item, "prompt", prompt_output);
        json_object_set(item, "revision", json_object_get(source, "_revision"));
        json_object_set(item, "run_id", json_object_get(source, "_run_id"));
        json_object_set(item, "title", json_object_get(source, "title"));
        json_array_append_new(array, item);
    }
    string_list_free(&ids);
    return array;
}

static json_t *selected_runs(const Store *store, const Search *search) {
    json_t *array = json_array();
    if (array == NULL) return NULL;
    for (size_t i = 0; i < store->group_count; ++i) {
        int tip = search->best[i];
        int *chain = NULL;
        size_t count = 0;
        for (int current = tip; current >= 0;
             current = store->runs[current].parent_index) {
            chain = xrealloc(chain, (count + 1) * sizeof(*chain));
            chain[count++] = current;
        }
        for (size_t j = count; j > 0; --j) {
            const Run *run = &store->runs[chain[j - 1]];
            json_t *entry = json_object();
            json_object_set_new(entry, "kind", json_string(run->kind));
            json_object_set_new(entry, "patch_sha256", json_string(run->digest));
            json_object_set_new(entry, "revision", json_integer(run->revision));
            json_object_set_new(entry, "run_id", json_string(run->run_id));
            json_object_set_new(entry, "target", json_string(run->target));
            json_array_append_new(array, entry);
        }
        free(chain);
    }
    return array;
}

static json_t *build_manifest(const Config *cfg, const Store *store,
                              const Search *search, const char *db_sha,
                              const char *yaml_sha, const char *toml_sha) {
    json_t *manifest = json_object();
    json_t *directions = json_array();
    json_t *source = json_object();
    json_t *walk = NULL;
    json_t *rooms = NULL;
    json_t *runs = NULL;
    if (manifest == NULL || directions == NULL || source == NULL ||
        build_walkthrough(cfg, search->best_rooms, search->best_puzzles, &walk) != 0 ||
        (rooms = manifest_rooms(cfg, search->best_rooms, search->best_puzzles)) == NULL ||
        (runs = selected_runs(store, search)) == NULL) goto fail;
    for (int i = 0; i < 4; ++i)
        json_array_append_new(directions, json_string(cfg->directions[i]));
    json_object_set_new(source, "experiment_id", json_integer(store->experiment_id));
    json_object_set_new(source, "maze_yaml_sha256", json_string(yaml_sha));
    json_object_set_new(source, "puzzles_toml_sha256", json_string(toml_sha));
    json_object_set_new(source, "selected_runs", runs); runs = NULL;
    json_object_set_new(source, "tracking_store_sha256", json_string(db_sha));
    json_object_set_new(manifest, "direction_order", directions); directions = NULL;
    json_object_set_new(manifest, "format", json_string("mlflow-maze-manifest-v1"));
    json_object_set_new(manifest, "goal_room", json_string(cfg->goal_room));
    json_object_set_new(manifest, "level_id", json_string(cfg->level_id));
    json_object_set_new(manifest, "rooms", rooms); rooms = NULL;
    json_object_set_new(manifest, "source", source); source = NULL;
    json_object_set_new(manifest, "start_room", json_string(cfg->start_room));
    json_object_set_new(manifest, "walkthrough", walk); walk = NULL;
    return manifest;
fail:
    json_decref(manifest); json_decref(directions); json_decref(source);
    json_decref(walk); json_decref(rooms); json_decref(runs);
    return NULL;
}

static int recover_level(const char *db_path, const char *yaml_path,
                         const char *toml_path, const char *output_path) {
    Config cfg;
    Store store;
    Search search;
    char db_sha[65], yaml_sha[65], toml_sha[65];
    json_t *manifest = NULL;
    char *serialized = NULL;
    char *with_newline = NULL;
    size_t length;
    int result = 5;
    memset(&store, 0, sizeof(store));
    memset(&search, 0, sizeof(search));
    if (load_config(yaml_path, toml_path, &cfg) != 0) return 2;
    if (sha256_file(db_path, db_sha) != 0 || sha256_file(yaml_path, yaml_sha) != 0 ||
        sha256_file(toml_path, toml_sha) != 0) {
        free_config(&cfg);
        return 5;
    }
    if (load_store(db_path, &cfg, &store) != 0) {
        free_config(&cfg);
        return 3;
    }
    if (select_level(&cfg, &store, &search) != 0) {
        result = 4;
        goto done;
    }
    manifest = build_manifest(&cfg, &store, &search, db_sha, yaml_sha, toml_sha);
    if (manifest == NULL) goto done;
    serialized = json_dumps(manifest, JSON_COMPACT | JSON_SORT_KEYS | JSON_ENSURE_ASCII);
    if (serialized == NULL) goto done;
    length = strlen(serialized);
    with_newline = malloc(length + 2);
    if (with_newline == NULL) goto done;
    memcpy(with_newline, serialized, length);
    with_newline[length] = '\n';
    with_newline[length + 1] = '\0';
    if (atomic_write(output_path, with_newline, length + 1) != 0) goto done;
    result = 0;
done:
    free(with_newline);
    free(serialized);
    json_decref(manifest);
    free_search(&search);
    free_store(&store);
    free_config(&cfg);
    return result;
}

static int manifest_to_state(json_t *manifest, Config *cfg) {
    json_t *format = json_object_get(manifest, "format");
    json_t *directions = json_object_get(manifest, "direction_order");
    json_t *room_array = json_object_get(manifest, "rooms");
    json_t *start = json_object_get(manifest, "start_room");
    json_t *goal = json_object_get(manifest, "goal_room");
    size_t index;
    json_t *item;
    memset(cfg, 0, sizeof(*cfg));
    if (!json_is_string(format) ||
        strcmp(json_string_value(format), "mlflow-maze-manifest-v1") != 0 ||
        !json_is_array(directions) || json_array_size(directions) != 4 ||
        !json_is_array(room_array) || !json_is_string(start) || !json_is_string(goal))
        return -1;
    cfg->start_room = xstrdup(json_string_value(start));
    cfg->goal_room = xstrdup(json_string_value(goal));
    cfg->rooms = json_object();
    cfg->puzzles = json_object();
    if (cfg->rooms == NULL || cfg->puzzles == NULL) return -1;
    for (int d = 0; d < 4; ++d) {
        json_t *direction = json_array_get(directions, (size_t)d);
        if (!json_is_string(direction) ||
            !direction_name(json_string_value(direction))) return -1;
        cfg->directions[d] = xstrdup(json_string_value(direction));
        for (int earlier = 0; earlier < d; ++earlier)
            if (strcmp(cfg->directions[earlier], cfg->directions[d]) == 0) return -1;
    }
    json_array_foreach(room_array, index, item) {
        json_t *id_node = json_object_get(item, "id");
        json_t *title = json_object_get(item, "title");
        json_t *exit_array = json_object_get(item, "exits");
        json_t *prompt = json_object_get(item, "prompt");
        json_t *room;
        json_t *exits;
        const char *id;
        size_t edge_index;
        json_t *edge;
        if (!json_is_object(item) || !json_is_string(id_node) ||
            !json_is_string(title) || !json_is_array(exit_array)) return -1;
        id = json_string_value(id_node);
        if (!valid_id(id) || json_object_get(cfg->rooms, id)) return -1;
        room = json_object();
        exits = json_object();
        json_object_set_new(room, "id", json_string(id));
        json_object_set(room, "title", title);
        json_object_set_new(room, "prompt_id", json_null());
        json_array_foreach(exit_array, edge_index, edge) {
            json_t *direction = json_object_get(edge, "direction");
            json_t *to = json_object_get(edge, "to");
            if (!json_is_string(direction) || !json_is_string(to) ||
                direction_index(cfg, json_string_value(direction)) < 0 ||
                json_object_get(exits, json_string_value(direction))) {
                json_decref(room); json_decref(exits); return -1;
            }
            json_object_set(exits, json_string_value(direction), to);
        }
        if (json_is_object(prompt)) {
            json_t *pid_node = json_object_get(prompt, "id");
            json_t *text = json_object_get(prompt, "prompt");
            json_t *answer = json_object_get(prompt, "answer_sha256");
            json_t *puzzle;
            const char *pid;
            if (!json_is_string(pid_node) || !json_is_string(text) ||
                !json_is_string(answer)) {
                json_decref(room); json_decref(exits); return -1;
            }
            pid = json_string_value(pid_node);
            puzzle = json_object_get(cfg->puzzles, pid);
            if (puzzle == NULL) {
                puzzle = json_object();
                json_object_set_new(puzzle, "id", json_string(pid));
                json_object_set(puzzle, "prompt", text);
                json_object_set(puzzle, "answer_sha256", answer);
                json_object_set_new(cfg->puzzles, pid, puzzle);
            } else if (!json_equal(json_object_get(puzzle, "prompt"), text) ||
                       !json_equal(json_object_get(puzzle, "answer_sha256"), answer)) {
                json_decref(room); json_decref(exits); return -1;
            }
            json_object_set_new(room, "prompt_id", json_string(pid));
        } else if (!json_is_null(prompt)) {
            json_decref(room); json_decref(exits); return -1;
        }
        json_object_set_new(room, "exits", exits);
        json_object_set_new(cfg->rooms, id, room);
    }
    return validate_state(cfg, cfg->rooms, cfg->puzzles) ? 0 : -1;
}

static int replay_manifest(const char *path) {
    unsigned char *data = NULL;
    size_t size = 0;
    json_error_t error;
    json_t *manifest = NULL;
    json_t *expected = NULL;
    json_t *actual;
    Config cfg;
    int result = 2;
    memset(&cfg, 0, sizeof(cfg));
    if (read_file(path, &data, &size) != 0) goto done;
    manifest = json_loadb((const char *)data, size, JSON_REJECT_DUPLICATES, &error);
    if (!json_is_object(manifest) || manifest_to_state(manifest, &cfg) != 0 ||
        build_walkthrough(&cfg, cfg.rooms, cfg.puzzles, &expected) != 0) goto done;
    actual = json_object_get(manifest, "walkthrough");
    if (!json_equal(expected, actual)) goto done;
    json_t *transcript = json_object_get(expected, "transcript");
    for (size_t i = 0; i < json_array_size(transcript); ++i)
        printf("%s\n", json_string_value(json_array_get(transcript, i)));
    printf("sha256 %s\n",
           json_string_value(json_object_get(expected, "sha256")));
    result = 0;
done:
    free(data);
    json_decref(manifest);
    json_decref(expected);
    free_config(&cfg);
    return result;
}

static int parse_recover_args(int argc, char **argv, const char **db,
                              const char **yaml, const char **toml,
                              const char **output) {
    if (argc != 10) return -1;
    for (int i = 2; i < argc; i += 2) {
        const char **slot = NULL;
        if (strcmp(argv[i], "--tracking-db") == 0) slot = db;
        else if (strcmp(argv[i], "--maze-yaml") == 0) slot = yaml;
        else if (strcmp(argv[i], "--puzzles-toml") == 0) slot = toml;
        else if (strcmp(argv[i], "--output") == 0) slot = output;
        else return -1;
        if (*slot != NULL) return -1;
        *slot = argv[i + 1];
    }
    if (!absolute_path(*db) || !absolute_path(*yaml) || !absolute_path(*toml) ||
        !absolute_path(*output) || strcmp(*output, *db) == 0 ||
        strcmp(*output, *yaml) == 0 || strcmp(*output, *toml) == 0) return -1;
    return 0;
}

int main(int argc, char **argv) {
    if (argc >= 2 && strcmp(argv[1], "recover") == 0) {
        const char *db = NULL;
        const char *yaml = NULL;
        const char *toml = NULL;
        const char *output = NULL;
        if (parse_recover_args(argc, argv, &db, &yaml, &toml, &output) != 0)
            return 2;
        return recover_level(db, yaml, toml, output);
    }
    if (argc == 4 && strcmp(argv[1], "replay") == 0 &&
        strcmp(argv[2], "--manifest") == 0 && absolute_path(argv[3])) {
        return replay_manifest(argv[3]);
    }
    return 2;
}
