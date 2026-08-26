const UPSTREAM: Record<number, number> = {
  110: 100,
  120: 100,
  100: 0,
};

export const MeshMap = {
  upstream(meshId: number): number {
    return UPSTREAM[meshId] ?? 0;
  },
};

export const BASIS: Record<number, number> = {
  10: 2,
  11: 3,
  12: 2,
};

export const SLICE_ID = 759;
