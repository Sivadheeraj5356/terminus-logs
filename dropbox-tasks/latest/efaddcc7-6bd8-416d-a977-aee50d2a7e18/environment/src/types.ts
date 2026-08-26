export type PlayerSpec = {
  id: number;
  start: [number, number];
  intent: [number, number];
};

export type MapSpec = {
  width: number;
  height: number;
  walls: number[][];
  players: PlayerSpec[];
};

export type CaseSpec = {
  id: string;
  map: string;
  epoch: number;
  salt: number;
  weight: number;
};

export type CaseRow = {
  id: string;
  epoch: number;
  digest: string;
  mix: number;
  cert: string;
  cells: number[];
  lit: number[];
};
