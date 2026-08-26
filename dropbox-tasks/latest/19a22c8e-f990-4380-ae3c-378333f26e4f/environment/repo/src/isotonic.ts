/*
 * Isotonic regression.
 *
 * Complete `fitPredict` so that, given one input, it fits an isotonic
 * regression to `(x, y)` (optionally sample-weighted) and returns the predicted
 * value at each query point, matching `sklearn.isotonic.IsotonicRegression` as
 * described in the task.
 *
 * `IsotonicInput` carries:
 *   - `x`: the training predictor values (ties allowed, any order)
 *   - `y`: the training response values (same length as x)
 *   - `weight`: per-sample weights (same length as x), or null for unit weights
 *   - `increasing`: fit a non-decreasing trend when true, non-increasing when false
 *   - `queries`: the points at which to predict, in the given order
 *
 * Return an array of predictions, one per query, in the same order.
 */

export interface IsotonicInput {
  x: number[];
  y: number[];
  weight: number[] | null;
  increasing: boolean;
  queries: number[];
}

// The stub returns zeros, which is not correct.
export function fitPredict(inp: IsotonicInput): number[] {
  return new Array<number>(inp.queries.length).fill(0.0);
}
