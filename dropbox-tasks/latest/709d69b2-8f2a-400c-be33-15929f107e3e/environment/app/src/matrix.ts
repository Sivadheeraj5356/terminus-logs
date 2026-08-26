export function solve3(matrix: number[][], vector: number[]): number[] {
  const a = matrix.map((row, i) => [...row, vector[i]]);
  for (let col = 0; col < 3; col += 1) {
    let pivot = col;
    for (let r = col + 1; r < 3; r += 1) {
      if (Math.abs(a[r][col]) > Math.abs(a[pivot][col])) pivot = r;
    }
    [a[col], a[pivot]] = [a[pivot], a[col]];
    const div = a[col][col];
    for (let c = col; c < 4; c += 1) a[col][c] /= div;
    for (let r = 0; r < 3; r += 1) {
      if (r === col) continue;
      const factor = a[r][col];
      for (let c = col; c < 4; c += 1) a[r][c] -= factor * a[col][c];
    }
  }
  return [a[0][3], a[1][3], a[2][3]];
}

export function invert3(matrix: number[][]): number[][] {
  const inverse: number[][] = [];
  for (let col = 0; col < 3; col += 1) {
    const rhs = [0, 0, 0];
    rhs[col] = 1;
    const solved = solve3(matrix, rhs);
    for (let row = 0; row < 3; row += 1) {
      if (!inverse[row]) inverse[row] = [];
      inverse[row][col] = solved[row];
    }
  }
  return inverse;
}
