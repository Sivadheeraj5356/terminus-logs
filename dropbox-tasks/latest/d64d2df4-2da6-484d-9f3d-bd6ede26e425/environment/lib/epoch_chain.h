#ifndef EPOCH_CHAIN_H
#define EPOCH_CHAIN_H

#include <stddef.h>

int epoch_chain_clear(void);
int epoch_chain_seed(const char *site, int scope);
int epoch_chain_publish(const char *site, int pub_a, int pub_b);
int epoch_chain_handoff(const char *site, int handoff_ord);
int epoch_chain_scope_sync(const char *site, int scope);
int epoch_chain_read(const char *site, int *scope, int *pub_a, int *pub_b, int *handoff_ord);
int epoch_chain_bind_seq(unsigned *out);
int epoch_chain_handoff_from_token(const char *token);
int epoch_chain_window_mod(const char *site, int *tick_out);

#endif
