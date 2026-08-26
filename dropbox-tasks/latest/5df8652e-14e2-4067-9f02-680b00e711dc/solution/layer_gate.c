#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BLOCK_SIZE 512u
#define MAX_LAYER_SIZE (8u * 1024u * 1024u)
#define MAX_MANIFEST_SIZE 65536u
#define MAX_LAYERS 16u
#define MAX_MEMBERS 4096u
#define MAX_PATH_BYTES 4096u

static const char *g_output_path;

static void fail(void) {
    if (g_output_path != NULL) {
        (void)remove(g_output_path);
    }
    exit(2);
}

static void *xmalloc(size_t size) {
    void *value = malloc(size == 0u ? 1u : size);
    if (value == NULL) {
        fail();
    }
    return value;
}

static void *xrealloc(void *pointer, size_t size) {
    void *value = realloc(pointer, size == 0u ? 1u : size);
    if (value == NULL) {
        fail();
    }
    return value;
}

static char *xstrndup(const char *text, size_t length) {
    char *value = xmalloc(length + 1u);
    memcpy(value, text, length);
    value[length] = '\0';
    return value;
}

static char *xstrdup(const char *text) {
    return xstrndup(text, strlen(text));
}

typedef struct {
    unsigned char *data;
    size_t length;
    size_t capacity;
} Buffer;

static void buffer_reserve(Buffer *buffer, size_t additional) {
    size_t required;
    size_t capacity;
    if (additional > SIZE_MAX - buffer->length) {
        fail();
    }
    required = buffer->length + additional;
    if (required <= buffer->capacity) {
        return;
    }
    capacity = buffer->capacity == 0u ? 256u : buffer->capacity;
    while (capacity < required) {
        if (capacity > SIZE_MAX / 2u) {
            capacity = required;
            break;
        }
        capacity *= 2u;
    }
    buffer->data = xrealloc(buffer->data, capacity);
    buffer->capacity = capacity;
}

static void buffer_bytes(Buffer *buffer, const void *data, size_t length) {
    buffer_reserve(buffer, length);
    memcpy(buffer->data + buffer->length, data, length);
    buffer->length += length;
}

static void buffer_text(Buffer *buffer, const char *text) {
    buffer_bytes(buffer, text, strlen(text));
}

static void buffer_char(Buffer *buffer, unsigned char value) {
    buffer_reserve(buffer, 1u);
    buffer->data[buffer->length++] = value;
}

static void buffer_format(Buffer *buffer, const char *format, ...) {
    va_list args;
    va_list copy;
    int needed;
    char *target;
    va_start(args, format);
    va_copy(copy, args);
    needed = vsnprintf(NULL, 0u, format, copy);
    va_end(copy);
    if (needed < 0) {
        va_end(args);
        fail();
    }
    buffer_reserve(buffer, (size_t)needed + 1u);
    target = (char *)buffer->data + buffer->length;
    if (vsnprintf(target, (size_t)needed + 1u, format, args) != needed) {
        va_end(args);
        fail();
    }
    va_end(args);
    buffer->length += (size_t)needed;
}

static void json_string(Buffer *buffer, const char *text) {
    const unsigned char *cursor = (const unsigned char *)text;
    buffer_char(buffer, '"');
    while (*cursor != 0u) {
        unsigned char value = *cursor++;
        if (value == '"' || value == '\\') {
            buffer_char(buffer, '\\');
            buffer_char(buffer, value);
        } else if (value == '\b') {
            buffer_text(buffer, "\\b");
        } else if (value == '\f') {
            buffer_text(buffer, "\\f");
        } else if (value == '\n') {
            buffer_text(buffer, "\\n");
        } else if (value == '\r') {
            buffer_text(buffer, "\\r");
        } else if (value == '\t') {
            buffer_text(buffer, "\\t");
        } else if (value < 0x20u) {
            buffer_format(buffer, "\\u%04x", (unsigned int)value);
        } else {
            buffer_char(buffer, value);
        }
    }
    buffer_char(buffer, '"');
}

typedef struct {
    uint32_t state[8];
    uint64_t bit_length;
    unsigned char block[64];
    size_t used;
} Sha256;

static uint32_t rotate_right(uint32_t value, unsigned int count) {
    return (value >> count) | (value << (32u - count));
}

static void sha256_transform(Sha256 *context, const unsigned char block[64]) {
    static const uint32_t constants[64] = {
        0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u,
        0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
        0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
        0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
        0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu,
        0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
        0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
        0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
        0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
        0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
        0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u,
        0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
        0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u,
        0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
        0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
        0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u
    };
    uint32_t words[64];
    uint32_t a;
    uint32_t b;
    uint32_t c;
    uint32_t d;
    uint32_t e;
    uint32_t f;
    uint32_t g;
    uint32_t h;
    size_t index;
    for (index = 0u; index < 16u; ++index) {
        size_t offset = index * 4u;
        words[index] = ((uint32_t)block[offset] << 24u) |
                       ((uint32_t)block[offset + 1u] << 16u) |
                       ((uint32_t)block[offset + 2u] << 8u) |
                       (uint32_t)block[offset + 3u];
    }
    for (index = 16u; index < 64u; ++index) {
        uint32_t s0 = rotate_right(words[index - 15u], 7u) ^
                      rotate_right(words[index - 15u], 18u) ^
                      (words[index - 15u] >> 3u);
        uint32_t s1 = rotate_right(words[index - 2u], 17u) ^
                      rotate_right(words[index - 2u], 19u) ^
                      (words[index - 2u] >> 10u);
        words[index] = words[index - 16u] + s0 + words[index - 7u] + s1;
    }
    a = context->state[0];
    b = context->state[1];
    c = context->state[2];
    d = context->state[3];
    e = context->state[4];
    f = context->state[5];
    g = context->state[6];
    h = context->state[7];
    for (index = 0u; index < 64u; ++index) {
        uint32_t sum1 = rotate_right(e, 6u) ^ rotate_right(e, 11u) ^ rotate_right(e, 25u);
        uint32_t choice = (e & f) ^ ((~e) & g);
        uint32_t temporary1 = h + sum1 + choice + constants[index] + words[index];
        uint32_t sum0 = rotate_right(a, 2u) ^ rotate_right(a, 13u) ^ rotate_right(a, 22u);
        uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
        uint32_t temporary2 = sum0 + majority;
        h = g;
        g = f;
        f = e;
        e = d + temporary1;
        d = c;
        c = b;
        b = a;
        a = temporary1 + temporary2;
    }
    context->state[0] += a;
    context->state[1] += b;
    context->state[2] += c;
    context->state[3] += d;
    context->state[4] += e;
    context->state[5] += f;
    context->state[6] += g;
    context->state[7] += h;
}

static void sha256_init(Sha256 *context) {
    static const uint32_t initial[8] = {
        0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
        0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u
    };
    memcpy(context->state, initial, sizeof(initial));
    context->bit_length = 0u;
    context->used = 0u;
}

static void sha256_update(Sha256 *context, const unsigned char *data, size_t length) {
    while (length > 0u) {
        size_t available = 64u - context->used;
        size_t amount = length < available ? length : available;
        memcpy(context->block + context->used, data, amount);
        context->used += amount;
        data += amount;
        length -= amount;
        if (context->used == 64u) {
            sha256_transform(context, context->block);
            context->bit_length += 512u;
            context->used = 0u;
        }
    }
}

static void sha256_finish(Sha256 *context, unsigned char digest[32]) {
    uint64_t total_bits = context->bit_length + (uint64_t)context->used * 8u;
    size_t index;
    context->block[context->used++] = 0x80u;
    if (context->used > 56u) {
        memset(context->block + context->used, 0, 64u - context->used);
        sha256_transform(context, context->block);
        context->used = 0u;
    }
    memset(context->block + context->used, 0, 56u - context->used);
    for (index = 0u; index < 8u; ++index) {
        context->block[63u - index] = (unsigned char)(total_bits >> (index * 8u));
    }
    sha256_transform(context, context->block);
    for (index = 0u; index < 8u; ++index) {
        digest[index * 4u] = (unsigned char)(context->state[index] >> 24u);
        digest[index * 4u + 1u] = (unsigned char)(context->state[index] >> 16u);
        digest[index * 4u + 2u] = (unsigned char)(context->state[index] >> 8u);
        digest[index * 4u + 3u] = (unsigned char)context->state[index];
    }
}

static void sha256_bytes(const unsigned char *data, size_t length, unsigned char digest[32]) {
    Sha256 context;
    sha256_init(&context);
    sha256_update(&context, data, length);
    sha256_finish(&context, digest);
}

static void hex_digest(const unsigned char digest[32], char output[65]) {
    static const char alphabet[] = "0123456789abcdef";
    size_t index;
    for (index = 0u; index < 32u; ++index) {
        output[index * 2u] = alphabet[digest[index] >> 4u];
        output[index * 2u + 1u] = alphabet[digest[index] & 15u];
    }
    output[64] = '\0';
}

static unsigned char *read_file(const char *path, size_t maximum, size_t *length) {
    FILE *file = fopen(path, "rb");
    long size;
    unsigned char *data;
    if (file == NULL || fseek(file, 0L, SEEK_END) != 0) {
        if (file != NULL) {
            fclose(file);
        }
        fail();
    }
    size = ftell(file);
    if (size < 0L || (unsigned long)size > (unsigned long)maximum || fseek(file, 0L, SEEK_SET) != 0) {
        fclose(file);
        fail();
    }
    data = xmalloc((size_t)size);
    if ((size_t)size > 0u && fread(data, 1u, (size_t)size, file) != (size_t)size) {
        fclose(file);
        fail();
    }
    if (fclose(file) != 0) {
        fail();
    }
    *length = (size_t)size;
    return data;
}

typedef struct {
    char digest[65];
    char *name;
} LayerRecord;

typedef struct {
    LayerRecord values[MAX_LAYERS];
    size_t count;
    char *directory;
    unsigned char manifest_digest[32];
} Manifest;

static int is_lower_hex(unsigned char value) {
    return (value >= '0' && value <= '9') || (value >= 'a' && value <= 'f');
}

static int is_manifest_name_byte(unsigned char value) {
    return (value >= 'A' && value <= 'Z') || (value >= 'a' && value <= 'z') ||
           (value >= '0' && value <= '9') || value == '.' || value == '_' || value == '-';
}

static char *directory_of(const char *path) {
    const char *slash = strrchr(path, '/');
    if (slash == NULL) {
        return xstrdup(".");
    }
    if (slash == path) {
        return xstrdup("/");
    }
    return xstrndup(path, (size_t)(slash - path));
}

static char *join_path(const char *directory, const char *name) {
    size_t left = strlen(directory);
    size_t right = strlen(name);
    int needs_slash = left > 0u && directory[left - 1u] != '/';
    char *result;
    if (left > SIZE_MAX - right - 2u) {
        fail();
    }
    result = xmalloc(left + right + (needs_slash ? 2u : 1u));
    memcpy(result, directory, left);
    if (needs_slash) {
        result[left++] = '/';
    }
    memcpy(result + left, name, right + 1u);
    return result;
}

static Manifest parse_manifest(const char *path) {
    Manifest manifest;
    unsigned char *data;
    size_t length;
    size_t cursor;
    size_t index;
    memset(&manifest, 0, sizeof(manifest));
    data = read_file(path, MAX_MANIFEST_SIZE, &length);
    sha256_bytes(data, length, manifest.manifest_digest);
    if (length < 8u || memcmp(data, "LAYERS2\n", 8u) != 0 || data[length - 1u] != '\n') {
        fail();
    }
    cursor = 8u;
    while (cursor < length) {
        size_t start = cursor;
        size_t line_length;
        char *name;
        while (cursor < length && data[cursor] != '\n') {
            ++cursor;
        }
        if (cursor >= length) {
            fail();
        }
        line_length = cursor - start;
        ++cursor;
        if (line_length < 66u || data[start + 64u] != ' ' || manifest.count >= MAX_LAYERS) {
            fail();
        }
        for (index = 0u; index < 64u; ++index) {
            if (!is_lower_hex(data[start + index])) {
                fail();
            }
            manifest.values[manifest.count].digest[index] = (char)data[start + index];
        }
        manifest.values[manifest.count].digest[64] = '\0';
        name = xstrndup((const char *)data + start + 65u, line_length - 65u);
        if (name[0] == '\0' || strcmp(name, ".") == 0 || strcmp(name, "..") == 0) {
            fail();
        }
        for (index = 0u; name[index] != '\0'; ++index) {
            if (!is_manifest_name_byte((unsigned char)name[index])) {
                fail();
            }
        }
        for (index = 0u; index < manifest.count; ++index) {
            if (strcmp(name, manifest.values[index].name) == 0) {
                fail();
            }
        }
        manifest.values[manifest.count].name = name;
        ++manifest.count;
    }
    if (manifest.count == 0u) {
        fail();
    }
    manifest.directory = directory_of(path);
    free(data);
    return manifest;
}

static uint64_t parse_octal(const unsigned char *field, size_t length) {
    size_t index = 0u;
    size_t digits;
    uint64_t value = 0u;
    while (index < length && field[index] == ' ') {
        ++index;
    }
    digits = index;
    while (index < length && field[index] >= '0' && field[index] <= '7') {
        if (value > (UINT64_MAX - 7u) / 8u) {
            fail();
        }
        value = value * 8u + (uint64_t)(field[index] - '0');
        ++index;
    }
    if (index == digits) {
        value = 0u;
    }
    while (index < length) {
        if (field[index] != 0u && field[index] != ' ') {
            fail();
        }
        ++index;
    }
    return value;
}

static char *header_string(const unsigned char *field, size_t length) {
    size_t used = 0u;
    size_t index;
    while (used < length && field[used] != 0u) {
        ++used;
    }
    if (used < length) {
        for (index = used + 1u; index < length; ++index) {
            if (field[index] != 0u) {
                fail();
            }
        }
    }
    return xstrndup((const char *)field, used);
}

static int printable_text(const char *text, int allow_empty) {
    const unsigned char *cursor = (const unsigned char *)text;
    size_t length = strlen(text);
    if ((!allow_empty && length == 0u) || length > MAX_PATH_BYTES) {
        return 0;
    }
    while (*cursor != 0u) {
        if (*cursor < 0x20u || *cursor > 0x7eu) {
            return 0;
        }
        ++cursor;
    }
    return 1;
}

static uint64_t parse_decimal_text(const char *text, uint64_t maximum) {
    uint64_t value = 0u;
    const unsigned char *cursor = (const unsigned char *)text;
    if (*cursor == 0u) {
        fail();
    }
    while (*cursor != 0u) {
        unsigned int digit;
        if (*cursor < '0' || *cursor > '9') {
            fail();
        }
        digit = (unsigned int)(*cursor - '0');
        if (value > (maximum - digit) / 10u) {
            fail();
        }
        value = value * 10u + digit;
        ++cursor;
    }
    return value;
}

static char *canonical_path(const char *raw) {
    char **parts;
    size_t part_count = 0u;
    size_t capacity = 16u;
    const char *cursor = raw;
    const char *start;
    Buffer result = {0};
    size_t index;
    if (raw[0] == '/') {
        return NULL;
    }
    parts = xmalloc(capacity * sizeof(*parts));
    while (1) {
        size_t length;
        start = cursor;
        while (*cursor != '\0' && *cursor != '/') {
            ++cursor;
        }
        length = (size_t)(cursor - start);
        if (length == 0u || (length == 1u && start[0] == '.')) {
            /* discarded */
        } else if (length == 2u && start[0] == '.' && start[1] == '.') {
            if (part_count == 0u) {
                free(parts);
                return NULL;
            }
            --part_count;
        } else {
            if (part_count == capacity) {
                capacity *= 2u;
                parts = xrealloc(parts, capacity * sizeof(*parts));
            }
            parts[part_count++] = xstrndup(start, length);
        }
        if (*cursor == '\0') {
            break;
        }
        ++cursor;
    }
    if (part_count == 0u) {
        free(parts);
        return NULL;
    }
    for (index = 0u; index < part_count; ++index) {
        if (index > 0u) {
            buffer_char(&result, '/');
        }
        buffer_text(&result, parts[index]);
    }
    buffer_char(&result, 0u);
    free(parts);
    return (char *)result.data;
}

typedef enum {
    MEMBER_FILE,
    MEMBER_DIRECTORY,
    MEMBER_SYMLINK,
    MEMBER_HARDLINK,
    MEMBER_WHITEOUT,
    MEMBER_OPAQUE
} MemberKind;

typedef struct {
    unsigned int layer;
    uint32_t offset;
    char *raw_path;
    char *path;
    char *raw_link;
    char *target;
    char *reject_reason;
    MemberKind kind;
    unsigned int mode;
    uint32_t uid;
    uint32_t gid;
    uint64_t size;
    unsigned char content_digest[32];
} Member;

typedef struct {
    Member *values;
    size_t count;
    size_t capacity;
} MemberList;

static Member *append_member(MemberList *list) {
    Member *value;
    if (list->count == list->capacity) {
        size_t capacity = list->capacity == 0u ? 32u : list->capacity * 2u;
        list->values = xrealloc(list->values, capacity * sizeof(*list->values));
        list->capacity = capacity;
    }
    value = &list->values[list->count++];
    memset(value, 0, sizeof(*value));
    return value;
}

typedef struct {
    char *path;
    char *linkpath;
    char *size;
    char *uid;
    char *gid;
} PaxState;

static void replace_string(char **target, const char *value, size_t length) {
    *target = xstrndup(value, length);
}

static int known_pax_key(const char *key, size_t length) {
    return (length == 4u && memcmp(key, "path", 4u) == 0) ||
           (length == 8u && memcmp(key, "linkpath", 8u) == 0) ||
           (length == 4u && memcmp(key, "size", 4u) == 0) ||
           (length == 3u && memcmp(key, "uid", 3u) == 0) ||
           (length == 3u && memcmp(key, "gid", 3u) == 0);
}

static void set_pax_value(PaxState *state, const char *key, size_t key_length,
                          const char *value, size_t value_length) {
    if (key_length == 4u && memcmp(key, "path", 4u) == 0) {
        replace_string(&state->path, value, value_length);
    } else if (key_length == 8u && memcmp(key, "linkpath", 8u) == 0) {
        replace_string(&state->linkpath, value, value_length);
    } else if (key_length == 4u && memcmp(key, "size", 4u) == 0) {
        replace_string(&state->size, value, value_length);
    } else if (key_length == 3u && memcmp(key, "uid", 3u) == 0) {
        replace_string(&state->uid, value, value_length);
    } else if (key_length == 3u && memcmp(key, "gid", 3u) == 0) {
        replace_string(&state->gid, value, value_length);
    } else if (known_pax_key(key, key_length)) {
        fail();
    }
}

static void parse_pax(PaxState *state, const unsigned char *data, size_t length) {
    size_t cursor = 0u;
    while (cursor < length) {
        size_t record_start = cursor;
        size_t digits = 0u;
        size_t record_length = 0u;
        size_t space;
        size_t end;
        size_t equals;
        while (cursor < length && data[cursor] >= '0' && data[cursor] <= '9') {
            unsigned int digit = (unsigned int)(data[cursor] - '0');
            if (record_length > (SIZE_MAX - digit) / 10u) {
                fail();
            }
            record_length = record_length * 10u + digit;
            ++cursor;
            ++digits;
        }
        if (digits == 0u || data[record_start] == '0' || cursor >= length || data[cursor] != ' ') {
            fail();
        }
        space = cursor++;
        if (record_length > length - record_start) {
            fail();
        }
        end = record_start + record_length;
        if (end <= cursor || data[end - 1u] != '\n') {
            fail();
        }
        equals = cursor;
        while (equals < end - 1u && data[equals] != '=') {
            ++equals;
        }
        if (equals == cursor || equals >= end - 1u) {
            fail();
        }
        (void)space;
        set_pax_value(state, (const char *)data + cursor, equals - cursor,
                      (const char *)data + equals + 1u, end - equals - 2u);
        cursor = end;
    }
}

static char *join_ustar_name(char *prefix, char *name) {
    char *value;
    size_t left;
    size_t right;
    if (prefix[0] == '\0') {
        return xstrdup(name);
    }
    left = strlen(prefix);
    right = strlen(name);
    value = xmalloc(left + right + 2u);
    memcpy(value, prefix, left);
    value[left] = '/';
    memcpy(value + left + 1u, name, right + 1u);
    return value;
}

static int zero_block(const unsigned char *block) {
    size_t index;
    for (index = 0u; index < BLOCK_SIZE; ++index) {
        if (block[index] != 0u) {
            return 0;
        }
    }
    return 1;
}

static char *long_value(const unsigned char *data, size_t length, int allow_empty) {
    size_t index;
    char *value;
    if (length == 0u || data[length - 1u] != 0u) {
        fail();
    }
    for (index = 0u; index + 1u < length; ++index) {
        if (data[index] == 0u) {
            fail();
        }
    }
    value = xstrndup((const char *)data, length - 1u);
    if (!printable_text(value, allow_empty)) {
        fail();
    }
    return value;
}

static MemberList parse_tar(const unsigned char *data, size_t length, unsigned int layer) {
    MemberList list = {0};
    PaxState pax = {0};
    char *long_path = NULL;
    char *long_link = NULL;
    size_t cursor = 0u;
    int ended = 0;
    if (length > MAX_LAYER_SIZE || length % BLOCK_SIZE != 0u) {
        fail();
    }
    while (cursor < length) {
        const unsigned char *header = data + cursor;
        uint64_t stored_checksum;
        uint64_t computed_checksum = 0u;
        uint64_t mode;
        uint64_t uid;
        uint64_t gid;
        uint64_t header_size;
        uint64_t effective_size;
        size_t payload_start;
        size_t payload_end;
        size_t padded_end;
        size_t index;
        unsigned char type;
        char *name;
        char *prefix;
        char *header_path;
        char *header_link;
        if (zero_block(header)) {
            if (cursor + BLOCK_SIZE * 2u > length || !zero_block(header + BLOCK_SIZE)) {
                fail();
            }
            for (index = cursor + BLOCK_SIZE * 2u; index < length; ++index) {
                if (data[index] != 0u) {
                    fail();
                }
            }
            ended = 1;
            break;
        }
        if (cursor > UINT32_MAX || memcmp(header + 257u, "ustar\0", 6u) != 0 ||
            memcmp(header + 263u, "00", 2u) != 0) {
            fail();
        }
        stored_checksum = parse_octal(header + 148u, 8u);
        for (index = 0u; index < BLOCK_SIZE; ++index) {
            computed_checksum += (index >= 148u && index < 156u) ? (uint64_t)' ' : header[index];
        }
        if (stored_checksum != computed_checksum) {
            fail();
        }
        mode = parse_octal(header + 100u, 8u);
        uid = parse_octal(header + 108u, 8u);
        gid = parse_octal(header + 116u, 8u);
        header_size = parse_octal(header + 124u, 12u);
        (void)parse_octal(header + 136u, 12u);
        if (mode > 07777u || uid > UINT32_MAX || gid > UINT32_MAX || header_size > MAX_LAYER_SIZE) {
            fail();
        }
        type = header[156u] == 0u ? (unsigned char)'0' : header[156u];
        name = header_string(header, 100u);
        prefix = header_string(header + 345u, 155u);
        header_path = join_ustar_name(prefix, name);
        header_link = header_string(header + 157u, 100u);
        effective_size = header_size;
        if (type != 'x' && type != 'L' && type != 'K' && pax.size != NULL) {
            effective_size = parse_decimal_text(pax.size, MAX_LAYER_SIZE);
        }
        payload_start = cursor + BLOCK_SIZE;
        if (effective_size > SIZE_MAX - payload_start) {
            fail();
        }
        payload_end = payload_start + (size_t)effective_size;
        if ((size_t)effective_size > SIZE_MAX - (BLOCK_SIZE - 1u)) {
            fail();
        }
        padded_end = payload_start + (((size_t)effective_size + BLOCK_SIZE - 1u) / BLOCK_SIZE) * BLOCK_SIZE;
        if (payload_end > length || padded_end > length) {
            fail();
        }
        for (index = payload_end; index < padded_end; ++index) {
            if (data[index] != 0u) {
                fail();
            }
        }
        if (type == 'x') {
            parse_pax(&pax, data + payload_start, (size_t)effective_size);
        } else if (type == 'L') {
            long_path = long_value(data + payload_start, (size_t)effective_size, 0);
        } else if (type == 'K') {
            long_link = long_value(data + payload_start, (size_t)effective_size, 1);
        } else {
            Member *member;
            char *raw_path;
            char *raw_link;
            const char *base;
            if (list.count >= MAX_MEMBERS ||
                (type != '0' && type != '1' && type != '2' && type != '5')) {
                fail();
            }
            if (type != '0' && effective_size != 0u) {
                fail();
            }
            raw_path = xstrdup(pax.path != NULL ? pax.path : (long_path != NULL ? long_path : header_path));
            raw_link = xstrdup(pax.linkpath != NULL ? pax.linkpath : (long_link != NULL ? long_link : header_link));
            if (!printable_text(raw_path, 0) || !printable_text(raw_link, 1)) {
                fail();
            }
            if (type == '1' && raw_link[0] == '\0') {
                fail();
            }
            member = append_member(&list);
            member->layer = layer;
            member->offset = (uint32_t)cursor;
            member->raw_path = raw_path;
            member->path = canonical_path(raw_path);
            member->raw_link = raw_link;
            member->mode = (unsigned int)mode;
            member->uid = pax.uid != NULL ? (uint32_t)parse_decimal_text(pax.uid, UINT32_MAX) : (uint32_t)uid;
            member->gid = pax.gid != NULL ? (uint32_t)parse_decimal_text(pax.gid, UINT32_MAX) : (uint32_t)gid;
            member->size = effective_size;
            member->kind = type == '0' ? MEMBER_FILE :
                           (type == '1' ? MEMBER_HARDLINK :
                            (type == '2' ? MEMBER_SYMLINK : MEMBER_DIRECTORY));
            if (member->path == NULL) {
                member->reject_reason = xstrdup("unsafe_path");
            }
            if (member->kind == MEMBER_FILE) {
                sha256_bytes(data + payload_start, (size_t)effective_size, member->content_digest);
            } else if (member->kind == MEMBER_HARDLINK) {
                member->target = canonical_path(raw_link);
                if (member->target == NULL) {
                    member->reject_reason = xstrdup("unsafe_link_target");
                }
            }
            if (member->path != NULL) {
                base = strrchr(member->path, '/');
                base = base == NULL ? member->path : base + 1;
                if (strncmp(base, ".wh.", 4u) == 0) {
                    if (member->kind != MEMBER_FILE || effective_size != 0u) {
                        member->reject_reason = xstrdup("invalid_whiteout");
                    } else if (strcmp(base, ".wh..wh..opq") == 0) {
                        member->kind = MEMBER_OPAQUE;
                    } else if (strlen(base) == 4u) {
                        member->reject_reason = xstrdup("invalid_whiteout");
                    } else {
                        member->kind = MEMBER_WHITEOUT;
                    }
                }
            }
            memset(&pax, 0, sizeof(pax));
            long_path = NULL;
            long_link = NULL;
        }
        cursor = padded_end;
    }
    if (!ended || pax.path != NULL || pax.linkpath != NULL || pax.size != NULL ||
        pax.uid != NULL || pax.gid != NULL || long_path != NULL || long_link != NULL) {
        fail();
    }
    return list;
}

typedef enum {
    NODE_FILE,
    NODE_DIRECTORY,
    NODE_SYMLINK,
    NODE_HARDLINK_PENDING,
    NODE_HARDLINK
} NodeKind;

typedef struct {
    char *path;
    char *raw_path;
    char *target;
    unsigned int layer;
    uint32_t offset;
    unsigned int mode;
    uint32_t uid;
    uint32_t gid;
    uint64_t size;
    unsigned char content_digest[32];
    int has_content;
    int failed;
    NodeKind kind;
} Node;

typedef struct {
    Node *values;
    size_t count;
    size_t capacity;
} NodeList;

typedef struct {
    char *action;
    char *path;
    char *raw_path;
    unsigned int layer;
    uint32_t offset;
    size_t removed_count;
} Action;

typedef struct {
    Action *values;
    size_t count;
    size_t capacity;
} ActionList;

typedef struct {
    char *raw_path;
    char *reason;
    unsigned int layer;
    uint32_t offset;
} Unsafe;

typedef struct {
    Unsafe *values;
    size_t count;
    size_t capacity;
} UnsafeList;

typedef struct {
    char *path;
    char *raw_path;
    char *reason;
    char *target;
    unsigned int layer;
    uint32_t offset;
} HardFailure;

typedef struct {
    HardFailure *values;
    size_t count;
    size_t capacity;
} HardFailureList;

typedef struct {
    size_t trusted_layers;
    char **protected_paths;
    size_t protected_count;
    size_t protected_capacity;
    unsigned char policy_digest[32];
} Policy;

typedef enum {
    FIND_EXTERNAL_SYMLINK,
    FIND_HARDLINK_ESCAPE,
    FIND_HARDLINK_FAILURE,
    FIND_MALFORMED_WHITEOUT,
    FIND_NAMESPACE_CONFUSION,
    FIND_PATH_ESCAPE,
    FIND_PRIVILEGE_ESCALATION,
    FIND_PROTECTED_MUTATION,
    FIND_SHADOWED_MEMBER,
    FIND_SYMLINK_PIVOT,
    FIND_WHITEOUT_ABUSE
} FindingKind;

typedef struct {
    FindingKind kind;
    unsigned int layer;
    uint32_t offset;
    unsigned int mode;
    char *action;
    char *ancestor;
    char *ancestor_kind;
    char *ancestor_source;
    char *first_source;
    char *path;
    char *property;
    char *protected_root;
    char *raw_path;
    char *raw_target;
    char *reason;
    char *target;
} Finding;

typedef struct {
    Finding *values;
    size_t count;
    size_t capacity;
} FindingList;

typedef struct {
    NodeList nodes;
    FindingList findings;
} GateState;

static void *append_record(void **values, size_t *count, size_t *capacity, size_t record_size) {
    unsigned char *base;
    void *record;
    if (*count == *capacity) {
        size_t next = *capacity == 0u ? 16u : *capacity * 2u;
        if (next > SIZE_MAX / record_size) {
            fail();
        }
        *values = xrealloc(*values, next * record_size);
        *capacity = next;
    }
    base = *values;
    record = base + *count * record_size;
    memset(record, 0, record_size);
    ++*count;
    return record;
}

static Node *append_node(NodeList *list) {
    return append_record((void **)&list->values, &list->count, &list->capacity, sizeof(*list->values));
}

static Finding *append_finding(FindingList *list, FindingKind kind,
                               unsigned int layer, uint32_t offset) {
    Finding *value = append_record((void **)&list->values, &list->count,
                                   &list->capacity, sizeof(*list->values));
    value->kind = kind;
    value->layer = layer;
    value->offset = offset;
    return value;
}

static long node_index(const NodeList *list, const char *path) {
    size_t index;
    for (index = 0u; index < list->count; ++index) {
        if (strcmp(list->values[index].path, path) == 0) {
            return (long)index;
        }
    }
    return -1L;
}

static int path_descends_from(const char *path, const char *parent) {
    size_t length = strlen(parent);
    if (length == 0u) {
        return 1;
    }
    return strncmp(path, parent, length) == 0 && path[length] == '/';
}

static void remove_node_at(NodeList *list, size_t index) {
    if (index + 1u < list->count) {
        memmove(&list->values[index], &list->values[index + 1u],
                (list->count - index - 1u) * sizeof(*list->values));
    }
    --list->count;
}

static size_t remove_scope(NodeList *list, const char *path, int descendants) {
    size_t count = 0u;
    size_t index = 0u;
    while (index < list->count) {
        int matches = strcmp(list->values[index].path, path) == 0 ||
                      (descendants && path_descends_from(list->values[index].path, path));
        if (matches) {
            remove_node_at(list, index);
            ++count;
        } else {
            ++index;
        }
    }
    return count;
}

static size_t remove_descendants(NodeList *list, const char *parent) {
    size_t count = 0u;
    size_t index = 0u;
    while (index < list->count) {
        if (strcmp(list->values[index].path, parent) != 0 &&
            path_descends_from(list->values[index].path, parent)) {
            remove_node_at(list, index);
            ++count;
        } else {
            ++index;
        }
    }
    return count;
}

static Node *conflicting_ancestor(NodeList *nodes, const char *path, char **ancestor_path) {
    const char *cursor = path;
    while ((cursor = strchr(cursor, '/')) != NULL) {
        char *ancestor = xstrndup(path, (size_t)(cursor - path));
        long index = node_index(nodes, ancestor);
        if (index >= 0L && nodes->values[(size_t)index].kind != NODE_DIRECTORY) {
            *ancestor_path = ancestor;
            return &nodes->values[(size_t)index];
        }
        ++cursor;
    }
    return NULL;
}

static char *source_string(unsigned int layer, uint32_t offset) {
    char *value = xmalloc(14u);
    if (snprintf(value, 14u, "%04x:%08x", layer, offset) != 13) {
        fail();
    }
    return value;
}

static char *parent_path(const char *path) {
    const char *slash = strrchr(path, '/');
    if (slash == NULL) {
        return xstrdup("");
    }
    return xstrndup(path, (size_t)(slash - path));
}

static const char *base_name(const char *path) {
    const char *slash = strrchr(path, '/');
    return slash == NULL ? path : slash + 1;
}

static char *whiteout_target(const char *path) {
    char *parent = parent_path(path);
    const char *base = base_name(path);
    const char *name = base + 4u;
    char *result;
    size_t size;
    if (parent[0] == '\0') {
        return xstrdup(name);
    }
    size = strlen(parent) + strlen(name) + 2u;
    result = xmalloc(size);
    if (snprintf(result, size, "%s/%s", parent, name) < 0) {
        fail();
    }
    return result;
}

static int paths_overlap(const char *left, const char *right) {
    return strcmp(left, right) == 0 || path_descends_from(left, right) ||
           path_descends_from(right, left);
}

static const char *node_kind_for_finding(NodeKind kind) {
    if (kind == NODE_FILE) {
        return "file";
    }
    if (kind == NODE_SYMLINK) {
        return "symlink";
    }
    if (kind == NODE_HARDLINK || kind == NODE_HARDLINK_PENDING) {
        return "hardlink";
    }
    if (kind == NODE_DIRECTORY) {
        return "directory";
    }
    fail();
    return "";
}

static void append_protected_findings(GateState *state, const Policy *policy,
                                      const Member *member, const char *path,
                                      const char *action, int whiteout) {
    size_t index;
    for (index = 0u; index < policy->protected_count; ++index) {
        if (paths_overlap(path, policy->protected_paths[index])) {
            Finding *finding = append_finding(&state->findings, FIND_PROTECTED_MUTATION,
                                              member->layer, member->offset);
            finding->action = xstrdup(action);
            finding->path = xstrdup(path);
            finding->protected_root = xstrdup(policy->protected_paths[index]);
            finding->raw_path = xstrdup(member->raw_path);
            if (whiteout) {
                Finding *abuse = append_finding(&state->findings, FIND_WHITEOUT_ABUSE,
                                                member->layer, member->offset);
                abuse->action = xstrdup(action);
                abuse->path = xstrdup(path);
                abuse->protected_root = xstrdup(policy->protected_paths[index]);
                abuse->raw_path = xstrdup(member->raw_path);
            }
        }
    }
}

static void process_markers(GateState *state, const Policy *policy,
                            const MemberList *members, int hostile) {
    size_t index;
    for (index = 0u; index < members->count; ++index) {
        const Member *member = &members->values[index];
        char *path;
        if (member->reject_reason != NULL ||
            (member->kind != MEMBER_WHITEOUT && member->kind != MEMBER_OPAQUE)) {
            continue;
        }
        if (member->kind == MEMBER_OPAQUE) {
            path = parent_path(member->path);
            if (hostile) {
                append_protected_findings(state, policy, member, path, "opaque", 1);
            }
            (void)remove_descendants(&state->nodes, path);
        } else {
            path = whiteout_target(member->path);
            if (hostile) {
                append_protected_findings(state, policy, member, path, "whiteout", 1);
            }
            (void)remove_scope(&state->nodes, path, 1);
        }
    }
}

static void insert_member_node(GateState *state, const Member *member) {
    Node *node;
    int removes_descendants = member->kind != MEMBER_DIRECTORY;
    (void)remove_scope(&state->nodes, member->path, removes_descendants);
    node = append_node(&state->nodes);
    node->path = xstrdup(member->path);
    node->raw_path = xstrdup(member->raw_path);
    node->layer = member->layer;
    node->offset = member->offset;
    node->mode = member->mode;
    node->uid = member->uid;
    node->gid = member->gid;
    node->size = member->size;
    if (member->kind == MEMBER_FILE) {
        node->kind = NODE_FILE;
        node->has_content = 1;
        memcpy(node->content_digest, member->content_digest, 32u);
    } else if (member->kind == MEMBER_DIRECTORY) {
        node->kind = NODE_DIRECTORY;
    } else if (member->kind == MEMBER_SYMLINK) {
        node->kind = NODE_SYMLINK;
        node->target = xstrdup(member->raw_link);
    } else if (member->kind == MEMBER_HARDLINK) {
        node->kind = NODE_HARDLINK_PENDING;
        node->target = xstrdup(member->target);
    } else {
        fail();
    }
}

static int compare_node_pointer_physical(const void *left, const void *right) {
    const Node *a = *(const Node *const *)left;
    const Node *b = *(const Node *const *)right;
    if (a->layer != b->layer) {
        return a->layer < b->layer ? -1 : 1;
    }
    if (a->offset != b->offset) {
        return a->offset < b->offset ? -1 : 1;
    }
    return 0;
}

static const char *resolve_hardlink(NodeList *nodes, Node *origin,
                                    unsigned char digest[32], uint64_t *size) {
    char **seen = xmalloc((nodes->count + 1u) * sizeof(*seen));
    size_t seen_count = 1u;
    const char *target = origin->target;
    seen[0] = origin->path;
    while (1) {
        long found = node_index(nodes, target);
        Node *node;
        size_t index;
        if (found < 0L) {
            return "missing_target";
        }
        node = &nodes->values[(size_t)found];
        if ((node->kind == NODE_FILE || node->kind == NODE_HARDLINK) && node->has_content) {
            memcpy(digest, node->content_digest, 32u);
            *size = node->size;
            return NULL;
        }
        if (node->kind != NODE_HARDLINK_PENDING) {
            return "nonregular_target";
        }
        for (index = 0u; index < seen_count; ++index) {
            if (strcmp(seen[index], node->path) == 0) {
                return "cycle";
            }
        }
        seen[seen_count++] = node->path;
        target = node->target;
    }
}

static void resolve_layer_hardlinks(GateState *state, const Policy *policy) {
    Node **pending;
    size_t pending_count = 0u;
    size_t index;
    pending = xmalloc(state->nodes.count * sizeof(*pending));
    for (index = 0u; index < state->nodes.count; ++index) {
        if (state->nodes.values[index].kind == NODE_HARDLINK_PENDING) {
            pending[pending_count++] = &state->nodes.values[index];
        }
    }
    if (pending_count > 1u) {
        qsort(pending, pending_count, sizeof(*pending), compare_node_pointer_physical);
    }
    for (index = 0u; index < pending_count; ++index) {
        Node *node = pending[index];
        unsigned char digest[32];
        uint64_t size = 0u;
        const char *reason = resolve_hardlink(&state->nodes, node, digest, &size);
        if (reason == NULL) {
            node->kind = NODE_HARDLINK;
            node->has_content = 1;
            node->size = size;
            memcpy(node->content_digest, digest, 32u);
        } else {
            node->failed = 1;
            if (node->layer >= policy->trusted_layers) {
                Finding *finding = append_finding(&state->findings, FIND_HARDLINK_FAILURE,
                                                  node->layer, node->offset);
                finding->path = xstrdup(node->path);
                finding->reason = xstrdup(reason);
                finding->target = xstrdup(node->target);
            }
        }
    }
    index = 0u;
    while (index < state->nodes.count) {
        if (state->nodes.values[index].failed) {
            remove_node_at(&state->nodes, index);
        } else {
            ++index;
        }
    }
}

static const char *external_symlink_reason(const char *path, const char *target) {
    size_t depth = 0u;
    size_t index;
    const char *cursor;
    if (target[0] == '\0') {
        return "empty_target";
    }
    if (target[0] == '/') {
        return "absolute_target";
    }
    for (index = 0u; path[index] != '\0'; ++index) {
        if (path[index] == '/') {
            ++depth;
        }
    }
    cursor = target;
    while (1) {
        const char *slash = strchr(cursor, '/');
        size_t length = slash == NULL ? strlen(cursor) : (size_t)(slash - cursor);
        if (length == 0u || (length == 1u && cursor[0] == '.')) {
        } else if (length == 2u && cursor[0] == '.' && cursor[1] == '.') {
            if (depth == 0u) {
                return "root_escape";
            }
            --depth;
        } else {
            ++depth;
        }
        if (slash == NULL) {
            break;
        }
        cursor = slash + 1u;
    }
    return NULL;
}

static long seen_path(char **paths, size_t count, const char *path) {
    size_t index;
    for (index = 0u; index < count; ++index) {
        if (strcmp(paths[index], path) == 0) {
            return (long)index;
        }
    }
    return -1L;
}

static void add_privilege_findings(GateState *state, const Member *member) {
    static const unsigned int masks[] = {04000u, 02000u};
    static const char *names[] = {"setuid", "setgid"};
    size_t index;
    for (index = 0u; index < 2u; ++index) {
        if ((member->mode & masks[index]) != 0u) {
            Finding *finding = append_finding(&state->findings, FIND_PRIVILEGE_ESCALATION,
                                              member->layer, member->offset);
            finding->mode = member->mode;
            finding->path = xstrdup(member->path);
            finding->property = xstrdup(names[index]);
            finding->raw_path = xstrdup(member->raw_path);
        }
    }
    if ((member->mode & 0002u) != 0u && (member->mode & 0111u) != 0u) {
        Finding *finding = append_finding(&state->findings, FIND_PRIVILEGE_ESCALATION,
                                          member->layer, member->offset);
        finding->mode = member->mode;
        finding->path = xstrdup(member->path);
        finding->property = xstrdup("world_writable_executable");
        finding->raw_path = xstrdup(member->raw_path);
    }
}

static void process_layer(GateState *state, const Policy *policy,
                          const MemberList *members, unsigned int layer) {
    size_t index;
    int hostile = layer >= policy->trusted_layers;
    char **seen_paths = xmalloc((members->count == 0u ? 1u : members->count) * sizeof(*seen_paths));
    uint32_t *seen_offsets = xmalloc((members->count == 0u ? 1u : members->count) * sizeof(*seen_offsets));
    size_t seen_count = 0u;
    for (index = 0u; index < members->count; ++index) {
        const Member *member = &members->values[index];
        Finding *finding;
        if (!hostile || member->reject_reason == NULL) {
            continue;
        }
        if (strcmp(member->reject_reason, "unsafe_path") == 0) {
            finding = append_finding(&state->findings, FIND_PATH_ESCAPE,
                                     member->layer, member->offset);
            finding->raw_path = xstrdup(member->raw_path);
        } else if (strcmp(member->reject_reason, "unsafe_link_target") == 0) {
            finding = append_finding(&state->findings, FIND_HARDLINK_ESCAPE,
                                     member->layer, member->offset);
            finding->raw_path = xstrdup(member->raw_path);
            finding->raw_target = xstrdup(member->raw_link);
        } else if (strcmp(member->reject_reason, "invalid_whiteout") == 0) {
            finding = append_finding(&state->findings, FIND_MALFORMED_WHITEOUT,
                                     member->layer, member->offset);
            finding->raw_path = xstrdup(member->raw_path);
            finding->reason = xstrdup("invalid_whiteout");
        }
    }
    process_markers(state, policy, members, hostile);
    for (index = 0u; index < members->count; ++index) {
        const Member *member = &members->values[index];
        Node *conflict;
        char *ancestor = NULL;
        long seen_index;
        if (member->reject_reason != NULL || member->kind == MEMBER_WHITEOUT ||
            member->kind == MEMBER_OPAQUE) {
            continue;
        }
        if (hostile) {
            seen_index = seen_path(seen_paths, seen_count, member->path);
            if (seen_index >= 0L) {
                Finding *finding = append_finding(&state->findings, FIND_SHADOWED_MEMBER,
                                                  member->layer, member->offset);
                finding->first_source = source_string(member->layer, seen_offsets[(size_t)seen_index]);
                finding->path = xstrdup(member->path);
                finding->raw_path = xstrdup(member->raw_path);
            } else {
                seen_paths[seen_count] = member->path;
                seen_offsets[seen_count++] = member->offset;
            }
            if (member->kind == MEMBER_SYMLINK) {
                const char *reason = external_symlink_reason(member->path, member->raw_link);
                if (reason != NULL) {
                    Finding *finding = append_finding(&state->findings, FIND_EXTERNAL_SYMLINK,
                                                      member->layer, member->offset);
                    finding->path = xstrdup(member->path);
                    finding->raw_path = xstrdup(member->raw_path);
                    finding->raw_target = xstrdup(member->raw_link);
                    finding->reason = xstrdup(reason);
                }
            }
            add_privilege_findings(state, member);
            append_protected_findings(state, policy, member, member->path,
                                      "create_or_replace", 0);
        }
        conflict = conflicting_ancestor(&state->nodes, member->path, &ancestor);
        if (conflict != NULL) {
            if (hostile) {
                FindingKind kind = conflict->kind == NODE_SYMLINK ?
                                   FIND_SYMLINK_PIVOT : FIND_NAMESPACE_CONFUSION;
                Finding *finding = append_finding(&state->findings, kind,
                                                  member->layer, member->offset);
                finding->ancestor = ancestor;
                finding->ancestor_source = source_string(conflict->layer, conflict->offset);
                finding->path = xstrdup(member->path);
                finding->raw_path = xstrdup(member->raw_path);
                if (kind == FIND_NAMESPACE_CONFUSION) {
                    finding->ancestor_kind = xstrdup(node_kind_for_finding(conflict->kind));
                }
            }
            continue;
        }
        insert_member_node(state, member);
    }
    resolve_layer_hardlinks(state, policy);
}

static int finding_property_order(const char *property) {
    if (property == NULL || strcmp(property, "setuid") == 0) {
        return 0;
    }
    if (strcmp(property, "setgid") == 0) {
        return 1;
    }
    return 2;
}

static int compare_findings(const void *left, const void *right) {
    const Finding *a = left;
    const Finding *b = right;
    if (a->layer != b->layer) {
        return a->layer < b->layer ? -1 : 1;
    }
    if (a->offset != b->offset) {
        return a->offset < b->offset ? -1 : 1;
    }
    if (a->kind == FIND_PRIVILEGE_ESCALATION && b->kind == FIND_PRIVILEGE_ESCALATION) {
        int aa = finding_property_order(a->property);
        int bb = finding_property_order(b->property);
        if (aa != bb) {
            return aa < bb ? -1 : 1;
        }
    }
    if (a->protected_root != NULL && b->protected_root != NULL) {
        return strcmp(a->protected_root, b->protected_root);
    }
    return 0;
}

static void write_source(Buffer *buffer, unsigned int layer, uint32_t offset) {
    buffer_format(buffer, "\"%04x:%08x\"", layer, offset);
}

static size_t canonical_decimal(const unsigned char *data, size_t length, size_t maximum) {
    size_t value = 0u;
    size_t index;
    if (length == 0u || (length > 1u && data[0] == '0')) {
        fail();
    }
    for (index = 0u; index < length; ++index) {
        unsigned int digit;
        if (data[index] < '0' || data[index] > '9') {
            fail();
        }
        digit = (unsigned int)(data[index] - '0');
        if (value > (maximum - digit) / 10u) {
            fail();
        }
        value = value * 10u + digit;
    }
    return value;
}

static void append_policy_root(Policy *policy, char *root) {
    if (policy->protected_count == policy->protected_capacity) {
        size_t next = policy->protected_capacity == 0u ? 8u : policy->protected_capacity * 2u;
        policy->protected_paths = xrealloc(policy->protected_paths,
                                           next * sizeof(*policy->protected_paths));
        policy->protected_capacity = next;
    }
    policy->protected_paths[policy->protected_count++] = root;
}

static Policy parse_policy(const char *path, size_t layer_count) {
    Policy policy;
    unsigned char *data;
    size_t length;
    size_t cursor;
    size_t line_start;
    memset(&policy, 0, sizeof(policy));
    data = read_file(path, MAX_MANIFEST_SIZE, &length);
    sha256_bytes(data, length, policy.policy_digest);
    if (length < 1u || data[length - 1u] != '\n') {
        fail();
    }
    if (length < 13u || memcmp(data, "OCI-POLICY-1\n", 13u) != 0) {
        fail();
    }
    cursor = 13u;
    line_start = cursor;
    while (cursor < length && data[cursor] != '\n') {
        ++cursor;
    }
    if (cursor >= length || cursor - line_start <= 15u ||
        memcmp(data + line_start, "trusted_layers ", 15u) != 0) {
        fail();
    }
    policy.trusted_layers = canonical_decimal(data + line_start + 15u,
                                              cursor - line_start - 15u,
                                              MAX_LAYERS);
    ++cursor;
    while (cursor < length) {
        char *raw;
        char *canonical;
        line_start = cursor;
        while (cursor < length && data[cursor] != '\n') {
            ++cursor;
        }
        if (cursor >= length || cursor - line_start <= 8u ||
            memcmp(data + line_start, "protect ", 8u) != 0) {
            fail();
        }
        raw = xstrndup((const char *)data + line_start + 8u,
                       cursor - line_start - 8u);
        if (!printable_text(raw, 0)) {
            fail();
        }
        canonical = canonical_path(raw);
        if (canonical == NULL || strcmp(canonical, raw) != 0) {
            fail();
        }
        if (policy.protected_count > 0u &&
            strcmp(policy.protected_paths[policy.protected_count - 1u], canonical) >= 0) {
            fail();
        }
        append_policy_root(&policy, canonical);
        ++cursor;
    }
    if (policy.protected_count == 0u || policy.trusted_layers >= layer_count) {
        fail();
    }
    free(data);
    return policy;
}

static const char *section_name(FindingKind kind) {
    static const char *names[] = {
        "external_symlink_targets",
        "hardlink_escape_attempts",
        "hardlink_resolution_failures",
        "malformed_whiteout_attempts",
        "namespace_confusion_attempts",
        "path_escape_attempts",
        "privilege_escalation_entries",
        "protected_path_mutations",
        "shadowed_member_attacks",
        "symlink_pivot_attempts",
        "whiteout_scope_abuses"
    };
    return names[(size_t)kind];
}

static void write_finding(Buffer *output, const Finding *finding) {
    if (finding->kind == FIND_EXTERNAL_SYMLINK) {
        buffer_format(output, "{\"layer\":\"%04x\",\"path\":", finding->layer);
        json_string(output, finding->path);
        buffer_text(output, ",\"raw_path\":");
        json_string(output, finding->raw_path);
        buffer_text(output, ",\"raw_target\":");
        json_string(output, finding->raw_target);
        buffer_text(output, ",\"reason\":");
        json_string(output, finding->reason);
    } else if (finding->kind == FIND_HARDLINK_ESCAPE) {
        buffer_format(output, "{\"layer\":\"%04x\",\"raw_path\":", finding->layer);
        json_string(output, finding->raw_path);
        buffer_text(output, ",\"raw_target\":");
        json_string(output, finding->raw_target);
    } else if (finding->kind == FIND_HARDLINK_FAILURE) {
        buffer_format(output, "{\"layer\":\"%04x\",\"path\":", finding->layer);
        json_string(output, finding->path);
        buffer_text(output, ",\"reason\":");
        json_string(output, finding->reason);
        buffer_text(output, ",\"source\":");
        write_source(output, finding->layer, finding->offset);
        buffer_text(output, ",\"target\":");
        json_string(output, finding->target);
        buffer_char(output, '}');
        return;
    } else if (finding->kind == FIND_MALFORMED_WHITEOUT) {
        buffer_format(output, "{\"layer\":\"%04x\",\"raw_path\":", finding->layer);
        json_string(output, finding->raw_path);
        buffer_text(output, ",\"reason\":");
        json_string(output, finding->reason);
    } else if (finding->kind == FIND_NAMESPACE_CONFUSION) {
        buffer_text(output, "{\"ancestor\":");
        json_string(output, finding->ancestor);
        buffer_text(output, ",\"ancestor_kind\":");
        json_string(output, finding->ancestor_kind);
        buffer_text(output, ",\"ancestor_source\":");
        json_string(output, finding->ancestor_source);
        buffer_format(output, ",\"layer\":\"%04x\",\"path\":", finding->layer);
        json_string(output, finding->path);
        buffer_text(output, ",\"raw_path\":");
        json_string(output, finding->raw_path);
    } else if (finding->kind == FIND_PATH_ESCAPE) {
        buffer_format(output, "{\"layer\":\"%04x\",\"raw_path\":", finding->layer);
        json_string(output, finding->raw_path);
    } else if (finding->kind == FIND_PRIVILEGE_ESCALATION) {
        buffer_format(output, "{\"layer\":\"%04x\",\"mode\":\"%04o\",\"path\":",
                      finding->layer, finding->mode);
        json_string(output, finding->path);
        buffer_text(output, ",\"property\":");
        json_string(output, finding->property);
        buffer_text(output, ",\"raw_path\":");
        json_string(output, finding->raw_path);
    } else if (finding->kind == FIND_PROTECTED_MUTATION ||
               finding->kind == FIND_WHITEOUT_ABUSE) {
        buffer_text(output, "{\"action\":");
        json_string(output, finding->action);
        buffer_format(output, ",\"layer\":\"%04x\",\"path\":", finding->layer);
        json_string(output, finding->path);
        buffer_text(output, ",\"protected_root\":");
        json_string(output, finding->protected_root);
        buffer_text(output, ",\"raw_path\":");
        json_string(output, finding->raw_path);
    } else if (finding->kind == FIND_SHADOWED_MEMBER) {
        buffer_text(output, "{\"first_source\":");
        json_string(output, finding->first_source);
        buffer_format(output, ",\"layer\":\"%04x\",\"path\":", finding->layer);
        json_string(output, finding->path);
        buffer_text(output, ",\"raw_path\":");
        json_string(output, finding->raw_path);
    } else if (finding->kind == FIND_SYMLINK_PIVOT) {
        buffer_text(output, "{\"ancestor\":");
        json_string(output, finding->ancestor);
        buffer_text(output, ",\"ancestor_source\":");
        json_string(output, finding->ancestor_source);
        buffer_format(output, ",\"layer\":\"%04x\",\"path\":", finding->layer);
        json_string(output, finding->path);
        buffer_text(output, ",\"raw_path\":");
        json_string(output, finding->raw_path);
    } else {
        fail();
    }
    buffer_text(output, ",\"source\":");
    write_source(output, finding->layer, finding->offset);
    buffer_char(output, '}');
}

static Buffer build_report(GateState *state, const Manifest *manifest, const Policy *policy) {
    Buffer output = {0};
    size_t kind;
    size_t index;
    char manifest_hex[65];
    char policy_hex[65];
    if (state->findings.count > 1u) {
        qsort(state->findings.values, state->findings.count,
              sizeof(*state->findings.values), compare_findings);
    }
    hex_digest(manifest->manifest_digest, manifest_hex);
    hex_digest(policy->policy_digest, policy_hex);
    buffer_char(&output, '{');
    for (kind = 0u; kind <= (size_t)FIND_PROTECTED_MUTATION; ++kind) {
        size_t emitted = 0u;
        if (kind > 0u) {
            buffer_char(&output, ',');
        }
        json_string(&output, section_name((FindingKind)kind));
        buffer_text(&output, ":[");
        for (index = 0u; index < state->findings.count; ++index) {
            if ((size_t)state->findings.values[index].kind == kind) {
                if (emitted++ > 0u) {
                    buffer_char(&output, ',');
                }
                write_finding(&output, &state->findings.values[index]);
            }
        }
        buffer_char(&output, ']');
    }
    buffer_text(&output, ",\"security_summary\":[{\"finding_count\":");
    buffer_format(&output, "%zu,\"manifest_sha256\":", state->findings.count);
    json_string(&output, manifest_hex);
    buffer_text(&output, ",\"policy_sha256\":");
    json_string(&output, policy_hex);
    buffer_format(&output, ",\"trusted_layers\":%zu,\"untrusted_layers\":%zu,\"verdict\":",
                  policy->trusted_layers, manifest->count - policy->trusted_layers);
    json_string(&output, state->findings.count == 0u ? "accept" : "deny");
    buffer_text(&output, "}]");
    for (kind = (size_t)FIND_SHADOWED_MEMBER; kind <= (size_t)FIND_WHITEOUT_ABUSE; ++kind) {
        size_t emitted = 0u;
        buffer_char(&output, ',');
        json_string(&output, section_name((FindingKind)kind));
        buffer_text(&output, ":[");
        for (index = 0u; index < state->findings.count; ++index) {
            if ((size_t)state->findings.values[index].kind == kind) {
                if (emitted++ > 0u) {
                    buffer_char(&output, ',');
                }
                write_finding(&output, &state->findings.values[index]);
            }
        }
        buffer_char(&output, ']');
    }
    buffer_text(&output, "}\n");
    return output;
}

static void write_report(const char *path, const Buffer *report) {
    FILE *file = fopen(path, "wb");
    if (file == NULL) {
        fail();
    }
    if (report->length > 0u && fwrite(report->data, 1u, report->length, file) != report->length) {
        fclose(file);
        fail();
    }
    if (fclose(file) != 0) {
        fail();
    }
}

int main(int argc, char **argv) {
    Manifest manifest;
    Policy policy;
    GateState state;
    size_t layer;
    Buffer report;
    memset(&state, 0, sizeof(state));
    if (argc != 4) {
        if (argc > 3) {
            (void)remove(argv[3]);
        }
        return 2;
    }
    g_output_path = argv[3];
    (void)remove(g_output_path);
    manifest = parse_manifest(argv[2]);
    policy = parse_policy(argv[1], manifest.count);
    for (layer = 0u; layer < manifest.count; ++layer) {
        char *path = join_path(manifest.directory, manifest.values[layer].name);
        size_t length;
        unsigned char *data = read_file(path, MAX_LAYER_SIZE, &length);
        unsigned char digest[32];
        char digest_hex[65];
        MemberList members;
        sha256_bytes(data, length, digest);
        hex_digest(digest, digest_hex);
        if (strcmp(digest_hex, manifest.values[layer].digest) != 0) {
            fail();
        }
        members = parse_tar(data, length, (unsigned int)layer);
        process_layer(&state, &policy, &members, (unsigned int)layer);
        free(data);
    }
    report = build_report(&state, &manifest, &policy);
    write_report(g_output_path, &report);
    return 0;
}
