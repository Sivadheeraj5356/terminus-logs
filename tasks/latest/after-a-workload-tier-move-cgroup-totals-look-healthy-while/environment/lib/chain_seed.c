#include "chain_seed.h"

#include "epoch_chain.h"

int chain_seed_for_site(const char *site, int link_inv, int rebind_epoch)
{
    (void)rebind_epoch;
    return epoch_chain_seed(site, link_inv);
}
