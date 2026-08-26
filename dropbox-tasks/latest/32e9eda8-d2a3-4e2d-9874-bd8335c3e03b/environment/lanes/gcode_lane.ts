import path from 'path';
import { fn_h2 } from '../h2k/flag_mux';

const tag = 'gcode';
const seed = path.basename(__filename).charCodeAt(0) + 17;
const [expandCount] = fn_h2(String(seed), { synth: tag, node: 'mid' }, 1);
process.stdout.write(String(expandCount));
