#include "trace_emit.h"

#include "../../lib/digest.h"

#include <stdio.h>
#include <string.h>

static void audit_hex(const char *prefix, const TraceRow *row, char *out, size_t cap) {
    char msg[512];
    const char *decision = row->admit.decision == DEPOT_DECISION_ADMIT ? "admit" : "deny";
    snprintf(msg, sizeof(msg), "%s|%s|%s|%s|%u|%d", prefix, row->principal, row->ticket_id, decision,
             row->floor_epoch, row->revoke_hit);
  depot_sha256_hex((const unsigned char *)msg, strlen(msg), out, cap);
}

int trace_emit_e(const char *path, const TraceRow *row) {
    if (!path || !row) {
        return -1;
    }
    char issuer_hex[65];
    char gate_hex[65];
    audit_hex("issuer", row, issuer_hex, sizeof(issuer_hex));
    audit_hex("gate", row, gate_hex, sizeof(gate_hex));

    FILE *fp = fopen(path, "w");
    if (!fp) {
        return -1;
    }
    const char *decision = row->admit.decision == DEPOT_DECISION_ADMIT ? "admit" : "deny";
    fprintf(fp,
            "{\n"
            "  \"schema\": \"depot-admission-v1\",\n"
            "  \"pack_id\": \"%s\",\n"
            "  \"floor_epoch\": %u,\n"
            "  \"principal\": \"%s\",\n"
            "  \"ticket_id\": \"%s\",\n"
            "  \"parent_id\": \"%s\",\n"
            "  \"ticket_epoch\": %u,\n"
            "  \"scope_mask\": %u,\n"
            "  \"action_mask\": %u,\n"
            "  \"decision\": \"%s\",\n"
            "  \"reason\": \"%s\",\n"
            "  \"mac_ok\": %s,\n"
            "  \"revoke_hit\": %s,\n"
            "  \"scope_ok\": %s,\n"
            "  \"epoch_ok\": %s,\n"
            "  \"issuer_audit_hex\": \"%s\",\n"
            "  \"gate_audit_hex\": \"%s\"\n"
            "}\n",
            row->pack_id, row->floor_epoch, row->principal, row->ticket_id, row->parent_id,
            row->ticket_epoch, row->scope_mask, row->action_mask, decision, row->admit.reason,
            row->mac_ok ? "true" : "false", row->revoke_hit ? "true" : "false",
            row->scope_ok ? "true" : "false", row->epoch_ok ? "true" : "false", issuer_hex,
            gate_hex);
    fclose(fp);
    return 0;
}
