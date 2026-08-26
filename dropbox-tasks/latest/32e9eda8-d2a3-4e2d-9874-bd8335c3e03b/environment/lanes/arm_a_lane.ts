import { fn_h2 } from '../h2k/flag_mux';

const tag = 'arm_a';
const seed = tag.charCodeAt(0) + tag.charCodeAt(2);
const [expandCount] = fn_h2(String(seed), { [tag]: tag }, 0);
process.stdout.write(String(expandCount));
