#include "proto_s5.h"

int h5_fold_decl(StampCtx *sc, uint32_t gen, const DeclSnap *decl, StampSnap *out)
{
	return fold_stamp(sc, gen, decl, out);
}
