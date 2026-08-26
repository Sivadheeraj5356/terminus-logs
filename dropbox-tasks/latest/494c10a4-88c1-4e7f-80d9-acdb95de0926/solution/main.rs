use std::collections::HashMap;
use std::env;
use std::fs;
use std::path::Path;

fn read_csv(path: &Path) -> Vec<Vec<String>> {
    let text = fs::read_to_string(path).expect("read csv");
    let mut rows = Vec::new();
    for line in text.lines() {
        let line = line.trim_end_matches('\r');
        if line.is_empty() {
            continue;
        }
        rows.push(line.split(',').map(|s| s.trim().to_string()).collect());
    }
    rows
}

struct Field {
    n: usize,
    v: Vec<i64>,
}

fn load_fields(dir: &Path) -> HashMap<String, Field> {
    let rows = read_csv(&dir.join("field.csv"));
    let mut cells: HashMap<String, Vec<(usize, usize, i64)>> = HashMap::new();
    let mut maxrc: HashMap<String, usize> = HashMap::new();
    for r in rows.iter().skip(1) {
        let sid = r[0].clone();
        let row = r[1].parse::<usize>().unwrap();
        let col = r[2].parse::<usize>().unwrap();
        let val = r[3].parse::<i64>().unwrap();
        cells.entry(sid.clone()).or_default().push((row, col, val));
        let m = maxrc.entry(sid).or_insert(0);
        if row > *m {
            *m = row;
        }
        if col > *m {
            *m = col;
        }
    }
    let mut out = HashMap::new();
    for (sid, list) in cells {
        let n = maxrc[&sid] + 1;
        let mut v = vec![0i64; n * n];
        for (r, c, val) in list {
            v[r * n + c] = val;
        }
        out.insert(sid, Field { n, v });
    }
    out
}

struct Simplex {
    filt: i64,
    dim: u8,
    verts: Vec<usize>,
}

fn grid_simplices(n: usize) -> (Vec<[usize; 1]>, Vec<[usize; 2]>, Vec<[usize; 3]>) {
    let mut verts = Vec::new();
    for r in 0..n {
        for c in 0..n {
            verts.push([r * n + c]);
        }
    }
    let mut edges = Vec::new();
    for r in 0..n {
        for c in 0..n {
            let v = r * n + c;
            if c + 1 < n {
                edges.push([v, v + 1]);
            }
            if r + 1 < n {
                edges.push([v, v + n]);
            }
        }
    }
    let mut tris = Vec::new();
    for r in 0..n - 1 {
        for c in 0..n - 1 {
            let a = r * n + c;
            let b = r * n + c + 1;
            let d = (r + 1) * n + c;
            let e = (r + 1) * n + c + 1;
            edges.push([a, e]);
            tris.push([a, b, e]);
            tris.push([a, d, e]);
        }
    }
    (verts, edges, tris)
}

fn sublevel_finite(
    n: usize,
    height: &[i64],
    verts: &[[usize; 1]],
    edges: &[[usize; 2]],
    tris: &[[usize; 3]],
) -> (Vec<i64>, Vec<i64>) {
    let mut simp: Vec<Simplex> = Vec::new();
    for s in verts {
        simp.push(Simplex { filt: height[s[0]], dim: 0, verts: vec![s[0]] });
    }
    for s in edges {
        let f = height[s[0]].max(height[s[1]]);
        simp.push(Simplex { filt: f, dim: 1, verts: vec![s[0], s[1]] });
    }
    for s in tris {
        let f = height[s[0]].max(height[s[1]]).max(height[s[2]]);
        simp.push(Simplex { filt: f, dim: 2, verts: vec![s[0], s[1], s[2]] });
    }
    simp.sort_by(|a, b| {
        a.filt
            .cmp(&b.filt)
            .then(a.dim.cmp(&b.dim))
            .then(a.verts.cmp(&b.verts))
    });
    let m = simp.len();
    let words = m.div_ceil(64);
    let mut vpos: HashMap<usize, usize> = HashMap::new();
    let mut epos: HashMap<(usize, usize), usize> = HashMap::new();
    for (i, s) in simp.iter().enumerate() {
        match s.dim {
            0 => {
                vpos.insert(s.verts[0], i);
            }
            1 => {
                epos.insert((s.verts[0], s.verts[1]), i);
            }
            _ => {}
        }
    }
    let mut cols: Vec<Vec<u64>> = vec![vec![0u64; words]; m];
    let set = |col: &mut Vec<u64>, bit: usize| {
        col[bit / 64] |= 1u64 << (bit % 64);
    };
    let _ = n;
    for (i, s) in simp.iter().enumerate() {
        match s.dim {
            1 => {
                set(&mut cols[i], vpos[&s.verts[0]]);
                set(&mut cols[i], vpos[&s.verts[1]]);
            }
            2 => {
                let a = s.verts[0];
                let b = s.verts[1];
                let c = s.verts[2];
                set(&mut cols[i], epos[&(a, b)]);
                set(&mut cols[i], epos[&(a, c)]);
                set(&mut cols[i], epos[&(b, c)]);
            }
            _ => {}
        }
    }
    let high_bit = |col: &[u64]| -> i64 {
        for w in (0..words).rev() {
            if col[w] != 0 {
                return (w * 64) as i64 + (63 - col[w].leading_zeros() as i64);
            }
        }
        -1
    };
    let is_zero = |col: &[u64]| col.iter().all(|&x| x == 0);
    let mut low_inv: HashMap<i64, usize> = HashMap::new();
    let mut ord0 = Vec::new();
    let mut ord1 = Vec::new();
    for j in 0..m {
        loop {
            if is_zero(&cols[j]) {
                break;
            }
            let low = high_bit(&cols[j]);
            if let Some(&pj) = low_inv.get(&low) {
                let (a, b) = if pj < j {
                    let (left, right) = cols.split_at_mut(j);
                    (&left[pj], &mut right[0])
                } else {
                    unreachable!()
                };
                for w in 0..words {
                    b[w] ^= a[w];
                }
            } else {
                low_inv.insert(low, j);
                let li = low as usize;
                let p = simp[li].dim;
                if p == 0 || p == 1 {
                    let birth = simp[li].filt;
                    let death = simp[j].filt;
                    if death > birth {
                        if p == 0 {
                            ord0.push(death - birth);
                        } else {
                            ord1.push(death - birth);
                        }
                    }
                }
                break;
            }
        }
    }
    (ord0, ord1)
}

fn stat4(mut lst: Vec<i64>) -> [i64; 4] {
    lst.sort_by(|a, b| b.cmp(a));
    let cnt = lst.len() as i64;
    let tot: i64 = lst.iter().sum();
    let mx = if lst.is_empty() { 0 } else { lst[0] };
    let sec = if lst.len() >= 2 { lst[1] } else { 0 };
    [cnt, tot, mx, sec]
}

fn features(f: &Field) -> [i64; 17] {
    let n = f.n;
    let (verts, edges, tris) = grid_simplices(n);
    let hf: Vec<i64> = f.v.clone();
    let hg: Vec<i64> = f.v.iter().map(|x| -x).collect();
    let (o0, o1) = sublevel_finite(n, &hf, &verts, &edges, &tris);
    let (r0, r1) = sublevel_finite(n, &hg, &verts, &edges, &tris);
    let vmin = *f.v.iter().min().unwrap();
    let vmax = *f.v.iter().max().unwrap();
    let m = o0.iter().chain(o1.iter()).copied().max().unwrap_or(0);
    let sigma = m / 4;
    let keep = |lst: &[i64]| -> Vec<i64> { lst.iter().copied().filter(|&p| p > sigma).collect() };
    let a = stat4(keep(&o0));
    let b = stat4(keep(&o1));
    let c = stat4(keep(&r0));
    let d = stat4(keep(&r1));
    [
        a[0], a[1], a[2], a[3], b[0], b[1], b[2], b[3], c[0], c[1], c[2], c[3], d[0], d[1], d[2],
        d[3], vmax - vmin,
    ]
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let dir = if args.len() > 1 {
        args[1].clone()
    } else {
        "/app/data".to_string()
    };
    let dir = Path::new(&dir);
    let fields = load_fields(dir);

    let ref_rows = read_csv(&dir.join("reference_labels.csv"));
    let mut refs: Vec<(String, String)> = ref_rows
        .iter()
        .skip(1)
        .map(|r| (r[0].clone(), r[1].clone()))
        .collect();
    refs.sort();
    let query_rows = read_csv(&dir.join("queries.csv"));
    let mut queries: Vec<String> = query_rows.iter().skip(1).map(|r| r[0].clone()).collect();
    queries.sort();

    let ref_feat: Vec<(String, String, [i64; 17])> = refs
        .iter()
        .map(|(id, g)| (id.clone(), g.clone(), features(&fields[id])))
        .collect();

    let mut out = String::new();
    for q in &queries {
        let fq = features(&fields[q]);
        let mut best: Option<(i64, usize)> = None;
        for (i, (_id, _g, fr)) in ref_feat.iter().enumerate() {
            let mut dist = 0i64;
            for t in 0..17 {
                dist += (fq[t] - fr[t]).abs();
            }
            match best {
                Some((bd, _)) if dist >= bd => {}
                _ => best = Some((dist, i)),
            }
        }
        let bi = best.unwrap().1;
        let rid = &ref_feat[bi].0;
        let grp = &ref_feat[bi].1;
        out.push_str(&format!("{} {} {}", q, rid, grp));
        for t in 0..17 {
            out.push_str(&format!(" {}", fq[t]));
        }
        out.push('\n');
    }
    print!("{}", out);
}
