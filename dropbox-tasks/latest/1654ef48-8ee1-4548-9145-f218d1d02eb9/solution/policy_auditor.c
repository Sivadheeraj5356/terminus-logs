#define _GNU_SOURCE
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>

#define MAX_FINDINGS 2048
#define MAX_LINES 4096
#define MAX_PATH_LEN 1024
#define MAX_FULL_PATH_LEN 4096
#define MAX_LINE_LEN 4096

typedef struct {
    char rule_id[64];
    char file[MAX_PATH_LEN];
    int line;
    char message[512];
} Finding;

typedef struct {
    const char *id;
    const char *name;
    const char *description;
} Rule;

static const Rule RULES[] = {
    {"SEC-CI-DEPLOY-WRITE", "Production workflow write trust", "Production workflow uses pull_request_target or write-all permissions"},
    {"SEC-IAM-WILDCARD", "Wildcard privilege policy", "Allow statement combines privileged wildcard actions with resource star"},
    {"SEC-K8S-HOST-ACCESS", "Kubernetes host access", "Production workload uses host namespace or hostPath access"},
    {"SEC-K8S-PRIVILEGED", "Kubernetes privileged container", "Production workload enables privileged execution"},
    {"SEC-PUBLIC-ADMIN", "Public administrative ingress", "Public ingress exposes an administrative port"},
    {"SEC-SHELL-CURL-EXEC", "Remote shell bootstrap", "Production script pipes downloaded content into a shell"},
    {"SEC-UNPINNED-ACTION", "Unpinned production action", "Production deployment workflow action is not pinned to a commit SHA"},
};

static Finding findings[MAX_FINDINGS];
static int finding_count = 0;

static char *xstrdup(const char *s) {
    size_t n = strlen(s) + 1;
    char *out = (char *)malloc(n);
    if (!out) {
        fprintf(stderr, "out of memory\n");
        exit(2);
    }
    memcpy(out, s, n);
    return out;
}

static void to_lower_copy(char *dst, const char *src, size_t cap) {
    size_t i = 0;
    for (; src[i] && i + 1 < cap; i++) {
        dst[i] = (char)tolower((unsigned char)src[i]);
    }
    dst[i] = '\0';
}

static int contains_ci(const char *text, const char *needle) {
    char lower[MAX_LINE_LEN];
    to_lower_copy(lower, text, sizeof(lower));
    return strstr(lower, needle) != NULL;
}

static void trim_newline(char *s) {
    size_t n = strlen(s);
    while (n > 0 && (s[n - 1] == '\n' || s[n - 1] == '\r')) {
        s[--n] = '\0';
    }
}

static void add_finding(const char *rule_id, const char *file, int line, const char *detail) {
    if (line <= 0 || finding_count >= MAX_FINDINGS) {
        return;
    }
    for (int i = 0; i < finding_count; i++) {
        if (findings[i].line == line
            && strcmp(findings[i].rule_id, rule_id) == 0
            && strcmp(findings[i].file, file) == 0) {
            return;
        }
    }
    Finding *f = &findings[finding_count++];
    snprintf(f->rule_id, sizeof(f->rule_id), "%s", rule_id);
    snprintf(f->file, sizeof(f->file), "%s", file);
    f->line = line;
    snprintf(f->message, sizeof(f->message), "%s in %s:%d", detail, file, line);
}

static int count_char(const char *s, char ch) {
    int count = 0;
    for (; *s; s++) {
        if (*s == ch) {
            count++;
        }
    }
    return count;
}

static int has_ext(const char *lower_path, const char *ext) {
    size_t lp = strlen(lower_path);
    size_t le = strlen(ext);
    return lp >= le && strcmp(lower_path + lp - le, ext) == 0;
}

static int is_media_or_binary(const char *lower_path) {
    const char *exts[] = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".gz", ".pdf", ".woff", ".woff2", ".ttf", NULL};
    for (int i = 0; exts[i]; i++) {
        if (has_ext(lower_path, exts[i])) {
            return 1;
        }
    }
    return 0;
}

static int skip_context(const char *lower_path) {
    if (is_media_or_binary(lower_path)) {
        return 1;
    }
    if (has_ext(lower_path, ".md") || strstr(lower_path, "/docs/") || strstr(lower_path, "readme")) {
        return 1;
    }
    if (strstr(lower_path, "/dev/") || strstr(lower_path, "/test/") || strstr(lower_path, "/tests/")
        || strstr(lower_path, "sandbox") || strstr(lower_path, "example")) {
        return 1;
    }
    return 0;
}

static int production_context(const char *lower_path, char **lines, int line_count) {
    if (skip_context(lower_path)) {
        return 0;
    }
    if (strstr(lower_path, "/prod/") || strstr(lower_path, "prod")
        || strstr(lower_path, "/infra/iam/") || strncmp(lower_path, "infra/iam/", 10) == 0) {
        return 1;
    }
    if (strstr(lower_path, ".github/workflows/") && strstr(lower_path, "deploy")) {
        return 1;
    }
    if (has_ext(lower_path, ".sh") && strstr(lower_path, "deploy")) {
        return 1;
    }
    for (int i = 0; i < line_count; i++) {
        if (contains_ci(lines[i], "environment: production") || contains_ci(lines[i], "namespace: production")) {
            return 1;
        }
        const char *trimmed = lines[i];
        while (*trimmed == ' ' || *trimmed == '\t') {
            trimmed++;
        }
        if (strstr(lower_path, ".github/workflows/") && trimmed == lines[i] && contains_ci(trimmed, "name:")
            && (contains_ci(lines[i], "deploy") || contains_ci(lines[i], "prod"))) {
            return 1;
        }
    }
    return 0;
}

static int parse_first_int_after_equals(const char *line, int fallback) {
    const char *p = strchr(line, '=');
    if (!p) {
        p = line;
    }
    while (*p && !isdigit((unsigned char)*p) && *p != '-') {
        p++;
    }
    if (!*p) {
        return fallback;
    }
    return atoi(p);
}

static int public_cidr_line(const char *lower) {
    return strstr(lower, "0.0.0.0/0") || strstr(lower, "::/0");
}

static int admin_port_intersects(int from_port, int to_port) {
    int admin_ports[] = {22, 3389, 5432, 3306, 6379, 9200, 9300};
    if (from_port < 0 || to_port < 0) {
        return 0;
    }
    if (from_port > to_port) {
        int tmp = from_port;
        from_port = to_port;
        to_port = tmp;
    }
    for (size_t i = 0; i < sizeof(admin_ports) / sizeof(admin_ports[0]); i++) {
        if (from_port <= admin_ports[i] && admin_ports[i] <= to_port) {
            return 1;
        }
    }
    return 0;
}

static void scan_terraform_ingress(const char *rel, char **lines, int line_count) {
    int in_ingress = 0;
    int in_rule_resource = 0;
    int depth = 0;
    int from_port = -1;
    int to_port = -1;
    int public_line = 0;
    int rule_requires_ingress_type = 0;
    int rule_is_ingress = 0;

    for (int i = 0; i < line_count; i++) {
        char lower[MAX_LINE_LEN];
        to_lower_copy(lower, lines[i], sizeof(lower));

        if (!in_ingress && !in_rule_resource && strstr(lower, "ingress") && strchr(lines[i], '{')) {
            in_ingress = 1;
            depth = 0;
            from_port = -1;
            to_port = -1;
            public_line = 0;
            rule_requires_ingress_type = 0;
            rule_is_ingress = 1;
        }
        if (!in_ingress && !in_rule_resource
            && (strstr(lower, "aws_security_group_rule") || strstr(lower, "aws_vpc_security_group_ingress_rule"))
            && strchr(lines[i], '{')) {
            in_rule_resource = 1;
            depth = 0;
            from_port = -1;
            to_port = -1;
            public_line = 0;
            rule_requires_ingress_type = strstr(lower, "aws_security_group_rule") != NULL;
            rule_is_ingress = strstr(lower, "aws_vpc_security_group_ingress_rule") != NULL;
        }

        if (in_ingress || in_rule_resource) {
            depth += count_char(lines[i], '{');
            depth -= count_char(lines[i], '}');
            if (in_rule_resource && strstr(lower, "type") && strstr(lower, "ingress")) {
                rule_is_ingress = 1;
            }
            if (in_rule_resource && strstr(lower, "type") && strstr(lower, "egress")) {
                rule_is_ingress = 0;
            }
            if (strstr(lower, "from_port")) {
                from_port = parse_first_int_after_equals(lines[i], from_port);
            }
            if (strstr(lower, "to_port")) {
                to_port = parse_first_int_after_equals(lines[i], to_port);
            }
            if (public_cidr_line(lower)) {
                public_line = i + 1;
            }
            if (depth <= 0) {
                int is_ingress_rule = in_ingress || !rule_requires_ingress_type || rule_is_ingress;
                if (public_line && is_ingress_rule && admin_port_intersects(from_port, to_port)) {
                    add_finding("SEC-PUBLIC-ADMIN", rel, public_line, "public administrative ingress");
                }
                in_ingress = 0;
                in_rule_resource = 0;
                rule_requires_ingress_type = 0;
                rule_is_ingress = 0;
            }
        }
    }
}

static int broad_resource_nearby(char **lines, int line_count, int index) {
    int start = index - 5;
    int end = index + 10;
    if (start < 0) {
        start = 0;
    }
    if (end >= line_count) {
        end = line_count - 1;
    }
    for (int i = start; i <= end; i++) {
        char lower[MAX_LINE_LEN];
        to_lower_copy(lower, lines[i], sizeof(lower));
        if (strstr(lower, "resource") && strstr(lower, "*")) {
            return 1;
        }
    }
    return 0;
}

static int allow_effect_nearby(char **lines, int line_count, int index) {
    int start = index - 12;
    int end = index + 6;
    if (start < 0) {
        start = 0;
    }
    if (end >= line_count) {
        end = line_count - 1;
    }
    for (int i = start; i <= end; i++) {
        char lower[MAX_LINE_LEN];
        to_lower_copy(lower, lines[i], sizeof(lower));
        if (strstr(lower, "effect") && strstr(lower, "allow")) {
            return 1;
        }
    }
    return 0;
}

static int critical_action_line(const char *lower, int action_context) {
    if (!action_context) {
        return 0;
    }
    const char *markers[] = {
        "iam:*", "kms:*", "s3:*", "ec2:*", "organizations:*",
        "iam:passrole", "sts:assumerole", NULL
    };
    for (int i = 0; markers[i]; i++) {
        if (strstr(lower, markers[i])) {
            return 1;
        }
    }
    if (strstr(lower, "action") && strstr(lower, "*")) {
        return 1;
    }
    return 0;
}

static void scan_iam_policy(const char *rel, char **lines, int line_count) {
    int in_action_list = 0;
    for (int i = 0; i < line_count; i++) {
        char lower[MAX_LINE_LEN];
        to_lower_copy(lower, lines[i], sizeof(lower));

        int action_context = in_action_list || strstr(lower, "action") || strstr(lower, "actions");
        if ((strstr(lower, "action") || strstr(lower, "actions")) && strchr(lines[i], '[') && !strchr(lines[i], ']')) {
            in_action_list = 1;
            action_context = 1;
        }
        if (critical_action_line(lower, action_context)
            && allow_effect_nearby(lines, line_count, i)
            && broad_resource_nearby(lines, line_count, i)) {
            add_finding("SEC-IAM-WILDCARD", rel, i + 1, "wildcard privilege policy");
        }
        if (in_action_list && strchr(lines[i], ']')) {
            in_action_list = 0;
        }
    }
}

static void scan_kubernetes(const char *rel, char **lines, int line_count) {
    for (int i = 0; i < line_count; i++) {
        char lower[MAX_LINE_LEN];
        to_lower_copy(lower, lines[i], sizeof(lower));
        if (strstr(lower, "privileged: true") || strstr(lower, "allowprivilegeescalation: true")) {
            add_finding("SEC-K8S-PRIVILEGED", rel, i + 1, "production privileged Kubernetes setting");
        }
        if (strstr(lower, "hostnetwork: true") || strstr(lower, "hostpid: true")
            || strstr(lower, "hostipc: true") || strstr(lower, "hostpath:")) {
            add_finding("SEC-K8S-HOST-ACCESS", rel, i + 1, "production Kubernetes host access");
        }
    }
}

static int is_hex40(const char *s) {
    for (int i = 0; i < 40; i++) {
        if (!isxdigit((unsigned char)s[i])) {
            return 0;
        }
    }
    return s[40] == '\0' || isspace((unsigned char)s[40]) || s[40] == '#';
}

static int unpinned_action_line(const char *line) {
    const char *uses = strstr(line, "uses:");
    if (!uses) {
        return 0;
    }
    const char *value = uses + 5;
    while (*value && isspace((unsigned char)*value)) {
        value++;
    }
    if (strncmp(value, "./", 2) == 0 || strncmp(value, "docker://", 9) == 0) {
        return 0;
    }
    const char *at = strchr(value, '@');
    if (!at) {
        return 1;
    }
    at++;
    return !is_hex40(at);
}

static void scan_workflow(const char *rel, char **lines, int line_count) {
    for (int i = 0; i < line_count; i++) {
        char lower[MAX_LINE_LEN];
        to_lower_copy(lower, lines[i], sizeof(lower));
        if (strstr(lower, "pull_request_target")) {
            add_finding("SEC-CI-DEPLOY-WRITE", rel, i + 1, "production workflow trusts pull_request_target");
        }
        if (strstr(lower, "permissions:") && strstr(lower, "write-all")) {
            add_finding("SEC-CI-DEPLOY-WRITE", rel, i + 1, "production workflow grants write-all permissions");
        }
        if (strstr(lower, "uses:") && unpinned_action_line(lower)) {
            add_finding("SEC-UNPINNED-ACTION", rel, i + 1, "production action is not commit-pinned");
        }
    }
}

static void scan_shell_script(const char *rel, char **lines, int line_count) {
    for (int i = 0; i < line_count; i++) {
        char lower[MAX_LINE_LEN];
        to_lower_copy(lower, lines[i], sizeof(lower));
        if ((strstr(lower, "curl") || strstr(lower, "wget")) && strstr(lower, "|")
            && (strstr(lower, " bash") || strstr(lower, " sh") || strstr(lower, "/bin/bash")
                || strstr(lower, "/bin/sh") || strstr(lower, "sudo bash") || strstr(lower, "sudo sh")
                || strstr(lower, "sudo /bin/bash") || strstr(lower, "sudo /bin/sh"))) {
            add_finding("SEC-SHELL-CURL-EXEC", rel, i + 1, "production remote shell bootstrap");
        }
    }
}

static void scan_file(const char *root, const char *rel) {
    char full[MAX_FULL_PATH_LEN];
    snprintf(full, sizeof(full), "%s/%s", root, rel);

    FILE *fp = fopen(full, "r");
    if (!fp) {
        return;
    }

    char *lines[MAX_LINES];
    int line_count = 0;
    char buf[MAX_LINE_LEN];
    while (line_count < MAX_LINES && fgets(buf, sizeof(buf), fp)) {
        trim_newline(buf);
        lines[line_count++] = xstrdup(buf);
    }
    fclose(fp);

    char lower_path[MAX_PATH_LEN];
    to_lower_copy(lower_path, rel, sizeof(lower_path));
    if (!skip_context(lower_path) && production_context(lower_path, lines, line_count)) {
        if (has_ext(lower_path, ".tf")) {
            scan_terraform_ingress(rel, lines, line_count);
            scan_iam_policy(rel, lines, line_count);
        } else if (has_ext(lower_path, ".json")) {
            scan_iam_policy(rel, lines, line_count);
        } else if (has_ext(lower_path, ".yaml") || has_ext(lower_path, ".yml")) {
            if (strstr(lower_path, ".github/workflows/")) {
                scan_workflow(rel, lines, line_count);
            } else {
                scan_kubernetes(rel, lines, line_count);
            }
        } else if (has_ext(lower_path, ".sh")) {
            scan_shell_script(rel, lines, line_count);
        }
    }

    for (int i = 0; i < line_count; i++) {
        free(lines[i]);
    }
}

static int cmp_names(const void *a, const void *b) {
    const char *const *sa = (const char *const *)a;
    const char *const *sb = (const char *const *)b;
    return strcmp(*sa, *sb);
}

static void scan_dir(const char *root, const char *rel) {
    char full[MAX_FULL_PATH_LEN];
    if (rel[0]) {
        snprintf(full, sizeof(full), "%s/%s", root, rel);
    } else {
        snprintf(full, sizeof(full), "%s", root);
    }

    DIR *dir = opendir(full);
    if (!dir) {
        fprintf(stderr, "cannot open directory %s: %s\n", full, strerror(errno));
        exit(2);
    }

    char *names[1024];
    int name_count = 0;
    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL && name_count < 1024) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) {
            continue;
        }
        names[name_count++] = xstrdup(entry->d_name);
    }
    closedir(dir);
    qsort(names, name_count, sizeof(char *), cmp_names);

    for (int i = 0; i < name_count; i++) {
        char child_rel[MAX_PATH_LEN];
        char child_full[MAX_FULL_PATH_LEN];
        if (rel[0]) {
            snprintf(child_rel, sizeof(child_rel), "%s/%s", rel, names[i]);
        } else {
            snprintf(child_rel, sizeof(child_rel), "%s", names[i]);
        }
        snprintf(child_full, sizeof(child_full), "%s/%s", root, child_rel);

        struct stat st;
        if (stat(child_full, &st) == 0) {
            if (S_ISDIR(st.st_mode)) {
                scan_dir(root, child_rel);
            } else if (S_ISREG(st.st_mode)) {
                char lower_path[MAX_PATH_LEN];
                to_lower_copy(lower_path, child_rel, sizeof(lower_path));
                if (!is_media_or_binary(lower_path)) {
                    scan_file(root, child_rel);
                }
            }
        }
        free(names[i]);
    }
}

static int cmp_findings(const void *a, const void *b) {
    const Finding *fa = (const Finding *)a;
    const Finding *fb = (const Finding *)b;
    int c = strcmp(fa->file, fb->file);
    if (c != 0) {
        return c;
    }
    if (fa->line != fb->line) {
        return fa->line - fb->line;
    }
    return strcmp(fa->rule_id, fb->rule_id);
}

static void json_escape(FILE *out, const char *s) {
    for (; *s; s++) {
        unsigned char ch = (unsigned char)*s;
        if (ch == '"') {
            fputs("\\\"", out);
        } else if (ch == '\\') {
            fputs("\\\\", out);
        } else if (ch == '\n') {
            fputs("\\n", out);
        } else if (ch == '\r') {
            fputs("\\r", out);
        } else if (ch == '\t') {
            fputs("\\t", out);
        } else if (ch < 32) {
            fprintf(out, "\\u%04x", ch);
        } else {
            fputc(ch, out);
        }
    }
}

static int mkdir_p(const char *dir) {
    char tmp[MAX_PATH_LEN];
    snprintf(tmp, sizeof(tmp), "%s", dir);
    size_t len = strlen(tmp);
    if (len == 0) {
        return 0;
    }
    if (tmp[len - 1] == '/') {
        tmp[len - 1] = '\0';
    }
    for (char *p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0';
            if (mkdir(tmp, 0777) != 0 && errno != EEXIST) {
                return -1;
            }
            *p = '/';
        }
    }
    if (mkdir(tmp, 0777) != 0 && errno != EEXIST) {
        return -1;
    }
    return 0;
}

static int ensure_parent_dir(const char *path) {
    char parent[MAX_PATH_LEN];
    snprintf(parent, sizeof(parent), "%s", path);
    char *slash = strrchr(parent, '/');
    if (!slash) {
        return 0;
    }
    *slash = '\0';
    if (parent[0] == '\0') {
        return 0;
    }
    return mkdir_p(parent);
}

static void write_sarif(const char *output_path) {
    qsort(findings, finding_count, sizeof(Finding), cmp_findings);
    if (ensure_parent_dir(output_path) != 0) {
        fprintf(stderr, "cannot create output directory for %s\n", output_path);
        exit(2);
    }

    FILE *out = fopen(output_path, "w");
    if (!out) {
        fprintf(stderr, "cannot write %s: %s\n", output_path, strerror(errno));
        exit(2);
    }

    fprintf(out, "{\n");
    fprintf(out, "  \"version\": \"2.1.0\",\n");
    fprintf(out, "  \"$schema\": \"https://json.schemastore.org/sarif-2.1.0.json\",\n");
    fprintf(out, "  \"runs\": [\n");
    fprintf(out, "    {\n");
    fprintf(out, "      \"tool\": {\"driver\": {\"name\": \"policy-auditor\", \"rules\": [\n");
    for (size_t i = 0; i < sizeof(RULES) / sizeof(RULES[0]); i++) {
        if (i > 0) {
            fprintf(out, ",\n");
        }
        fprintf(out, "        {\"id\": \"");
        json_escape(out, RULES[i].id);
        fprintf(out, "\", \"name\": \"");
        json_escape(out, RULES[i].name);
        fprintf(out, "\", \"shortDescription\": {\"text\": \"");
        json_escape(out, RULES[i].description);
        fprintf(out, "\"}}");
    }
    fprintf(out, "\n      ]}},\n");
    fprintf(out, "      \"results\": [\n");
    for (int i = 0; i < finding_count; i++) {
        if (i > 0) {
            fprintf(out, ",\n");
        }
        fprintf(out, "        {\"ruleId\": \"");
        json_escape(out, findings[i].rule_id);
        fprintf(out, "\", \"message\": {\"text\": \"");
        json_escape(out, findings[i].message);
        fprintf(out, "\"}, \"locations\": [{\"physicalLocation\": {\"artifactLocation\": {\"uri\": \"");
        json_escape(out, findings[i].file);
        fprintf(out, "\"}, \"region\": {\"startLine\": %d}}}]}", findings[i].line);
    }
    fprintf(out, "\n      ]\n");
    fprintf(out, "    }\n");
    fprintf(out, "  ]\n");
    fprintf(out, "}\n");
    fclose(out);
}

int main(int argc, char **argv) {
    const char *repo_dir = "/app/task_file/input_data/repo";
    const char *output_path = "/app/task_file/output_data/findings.sarif";
    if (argc == 3) {
        repo_dir = argv[1];
        output_path = argv[2];
    } else if (argc != 1) {
        fprintf(stderr, "usage: policy-auditor [repo_dir sarif_output]\n");
        return 2;
    }

    scan_dir(repo_dir, "");
    write_sarif(output_path);
    return 0;
}
