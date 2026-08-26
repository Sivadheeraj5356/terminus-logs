use std::collections::{HashMap, HashSet};
use std::env;
use std::fs;
use std::io::Write;
use std::ffi::OsString;
use std::path::{Component, Path, PathBuf};

#[derive(Clone, Debug)]
struct Case {
    name: String,
    modes: usize,
    mu_max: f64,
    mu_step: f64,
    l1: f64,
    k1: f64,
    alpha1: f64,
    c1: f64,
    l2: f64,
    k2: f64,
    alpha2: f64,
    c2: f64,
    l3: f64,
    k3: f64,
    alpha3: f64,
    c3: f64,
    r12: f64,
    s12: f64,
    r23: f64,
    s23: f64,
    h_left: f64,
    b_left: f64,
    h_right: f64,
    b_right: f64,
}

#[derive(Clone, Copy, Debug)]
struct State {
    phi: f64,
    q: f64,
}

#[derive(Clone, Copy, Debug)]
struct Trace {
    left: State,
    i1_left: State,
    i1_right: State,
    i2_left: State,
    i2_right: State,
    right: State,
}

#[derive(Clone, Debug)]
struct Mode {
    index: usize,
    eigenvalue: f64,
    left_amplitude: f64,
    interface1_left: f64,
    interface1_right: f64,
    interface2_left: f64,
    interface2_right: f64,
    right_amplitude: f64,
    interface1_flux_left: f64,
    interface1_flux_right: f64,
    interface2_flux_left: f64,
    interface2_flux_right: f64,
    sensitivity_h_right: f64,
    sensitivity_r12: f64,
    modal_heat_content: f64,
}

fn fail(message: impl AsRef<str>) -> ! {
    eprintln!("thermal_modes: {}", message.as_ref());
    std::process::exit(2);
}

fn parse_cli() -> (PathBuf, PathBuf) {
    let mut input: Option<PathBuf> = None;
    let mut output: Option<PathBuf> = None;
    let mut args = env::args().skip(1);
    while let Some(argument) = args.next() {
        match argument.as_str() {
            "--input-dir" => {
                if input.is_some() {
                    fail("duplicate --input-dir");
                }
                let value = args.next().unwrap_or_else(|| fail("--input-dir requires a value"));
                input = Some(PathBuf::from(value));
            }
            "--output-dir" => {
                if output.is_some() {
                    fail("duplicate --output-dir");
                }
                let value = args.next().unwrap_or_else(|| fail("--output-dir requires a value"));
                output = Some(PathBuf::from(value));
            }
            _ => fail(format!("unknown argument: {argument}")),
        }
    }
    (
        input.unwrap_or_else(|| fail("missing --input-dir")),
        output.unwrap_or_else(|| fail("missing --output-dir")),
    )
}

fn parse_f64(values: &HashMap<String, String>, key: &str) -> f64 {
    let text = values.get(key).unwrap_or_else(|| fail(format!("missing key: {key}")));
    let value: f64 = text.parse().unwrap_or_else(|_| fail(format!("invalid float for {key}: {text}")));
    if !value.is_finite() {
        fail(format!("non-finite value for {key}"));
    }
    value
}

fn require_positive(value: f64, key: &str) -> f64 {
    if value <= 0.0 {
        fail(format!("{key} must be positive"));
    }
    value
}

fn require_nonnegative(value: f64, key: &str) -> f64 {
    if value < 0.0 {
        fail(format!("{key} must be nonnegative"));
    }
    value
}

fn parse_case(path: &Path) -> Case {
    let raw = fs::read_to_string(path).unwrap_or_else(|error| fail(format!("cannot read {}: {error}", path.display())));
    let mut values: HashMap<String, String> = HashMap::new();
    for (line_index, line) in raw.lines().enumerate() {
        if line.is_empty() || line.trim() != line {
            fail(format!("{}:{}: blank line or surrounding whitespace", path.display(), line_index + 1));
        }
        let (key, value) = line
            .split_once('=')
            .unwrap_or_else(|| fail(format!("{}:{}: expected key=value", path.display(), line_index + 1)));
        if key.is_empty() || value.is_empty() || key.trim() != key || value.trim() != value {
            fail(format!("{}:{}: malformed key=value", path.display(), line_index + 1));
        }
        if values.insert(key.to_string(), value.to_string()).is_some() {
            fail(format!("{}:{}: duplicate key {key}", path.display(), line_index + 1));
        }
    }

    const KEYS: [&str; 24] = [
        "name", "modes", "mu_max", "mu_step", "L1", "k1", "alpha1", "c1", "L2", "k2",
        "alpha2", "c2", "L3", "k3", "alpha3", "c3", "R12", "S12", "R23", "S23",
        "h_left", "b_left", "h_right", "b_right",
    ];
    let expected: HashSet<&str> = KEYS.iter().copied().collect();
    let actual: HashSet<&str> = values.keys().map(String::as_str).collect();
    if actual != expected {
        let mut missing: Vec<&str> = expected.difference(&actual).copied().collect();
        let mut extra: Vec<&str> = actual.difference(&expected).copied().collect();
        missing.sort_unstable();
        extra.sort_unstable();
        fail(format!("{}: key mismatch; missing={missing:?} extra={extra:?}", path.display()));
    }

    let name = values.get("name").unwrap().clone();
    if name.is_empty()
        || !name
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'_' || byte == b'-')
    {
        fail(format!("{}: invalid case name", path.display()));
    }
    let modes: usize = values
        .get("modes")
        .unwrap()
        .parse()
        .unwrap_or_else(|_| fail(format!("{}: invalid modes", path.display())));
    if !(1..=20).contains(&modes) {
        fail(format!("{}: modes must be in 1..=20", path.display()));
    }

    let mu_max = require_positive(parse_f64(&values, "mu_max"), "mu_max");
    let mu_step = require_positive(parse_f64(&values, "mu_step"), "mu_step");
    if mu_step >= mu_max || mu_step > 0.02 {
        fail(format!("{}: invalid mu search interval", path.display()));
    }

    Case {
        name,
        modes,
        mu_max,
        mu_step,
        l1: require_positive(parse_f64(&values, "L1"), "L1"),
        k1: require_positive(parse_f64(&values, "k1"), "k1"),
        alpha1: require_positive(parse_f64(&values, "alpha1"), "alpha1"),
        c1: require_positive(parse_f64(&values, "c1"), "c1"),
        l2: require_positive(parse_f64(&values, "L2"), "L2"),
        k2: require_positive(parse_f64(&values, "k2"), "k2"),
        alpha2: require_positive(parse_f64(&values, "alpha2"), "alpha2"),
        c2: require_positive(parse_f64(&values, "c2"), "c2"),
        l3: require_positive(parse_f64(&values, "L3"), "L3"),
        k3: require_positive(parse_f64(&values, "k3"), "k3"),
        alpha3: require_positive(parse_f64(&values, "alpha3"), "alpha3"),
        c3: require_positive(parse_f64(&values, "c3"), "c3"),
        r12: require_nonnegative(parse_f64(&values, "R12"), "R12"),
        s12: require_nonnegative(parse_f64(&values, "S12"), "S12"),
        r23: require_nonnegative(parse_f64(&values, "R23"), "R23"),
        s23: require_nonnegative(parse_f64(&values, "S23"), "S23"),
        h_left: require_nonnegative(parse_f64(&values, "h_left"), "h_left"),
        b_left: require_nonnegative(parse_f64(&values, "b_left"), "b_left"),
        h_right: require_nonnegative(parse_f64(&values, "h_right"), "h_right"),
        b_right: require_nonnegative(parse_f64(&values, "b_right"), "b_right"),
    }
}

fn propagate(state: State, k: f64, alpha: f64, length: f64, lambda: f64) -> State {
    let omega = (lambda / alpha).sqrt();
    let phase = omega * length;
    let cosine = phase.cos();
    let sine = phase.sin();
    State {
        phi: cosine * state.phi + sine * state.q / (k * omega),
        q: -k * omega * sine * state.phi + cosine * state.q,
    }
}

fn cross_interface(state: State, resistance: f64, sheet_capacity: f64, lambda: f64) -> State {
    let phi = state.phi - resistance * state.q;
    State {
        phi,
        q: state.q - sheet_capacity * lambda * phi,
    }
}

fn trace(case: &Case, lambda: f64) -> Trace {
    let left = State {
        phi: 1.0,
        q: case.h_left - case.b_left * lambda,
    };
    let i1_left = propagate(left, case.k1, case.alpha1, case.l1, lambda);
    let i1_right = cross_interface(i1_left, case.r12, case.s12, lambda);
    let i2_left = propagate(i1_right, case.k2, case.alpha2, case.l2, lambda);
    let i2_right = cross_interface(i2_left, case.r23, case.s23, lambda);
    let right = propagate(i2_right, case.k3, case.alpha3, case.l3, lambda);
    Trace {
        left,
        i1_left,
        i1_right,
        i2_left,
        i2_right,
        right,
    }
}

fn determinant(case: &Case, lambda: f64) -> f64 {
    let end = trace(case, lambda).right;
    end.q + case.h_right * end.phi - case.b_right * lambda * end.phi
}

fn signs_differ(left: f64, right: f64) -> bool {
    left.is_sign_positive() != right.is_sign_positive()
}

fn refine_bracket(case: &Case, mut left: f64, mut right: f64, mut f_left: f64) -> f64 {
    let f_right = determinant(case, right * right);
    if !f_right.is_finite() || !f_left.is_finite() || !signs_differ(f_left, f_right) {
        fail(format!("{}: invalid root bracket", case.name));
    }
    for _ in 0..120 {
        let middle = 0.5 * (left + right);
        let f_middle = determinant(case, middle * middle);
        if !f_middle.is_finite() {
            fail(format!("{}: non-finite determinant during root refinement", case.name));
        }
        if signs_differ(f_left, f_middle) {
            right = middle;
        } else {
            left = middle;
            f_left = f_middle;
        }
    }
    0.5 * (left + right)
}

fn first_roots(case: &Case) -> Vec<f64> {
    let mut roots_mu: Vec<f64> = Vec::with_capacity(case.modes);

    // mu_step is only a coarse-resolution upper bound.  A much finer independent
    // isolation mesh is required because several simple roots can occur inside
    // one supplied interval.  Valid task cases guarantee at least 1e-4 spacing
    // in mu, so a 2.5e-5 ceiling supplies at least four samples across that gap.
    let isolation_step = case.mu_step.min(2.5e-5_f64);
    let mut mu_left = 1.0e-7_f64;
    let mut f_left = determinant(case, mu_left * mu_left);
    if !f_left.is_finite() {
        fail(format!("{}: non-finite determinant at scan start", case.name));
    }

    while mu_left < case.mu_max && roots_mu.len() < case.modes {
        let mu_right = (mu_left + isolation_step).min(case.mu_max);
        let f_right = determinant(case, mu_right * mu_right);
        if !f_right.is_finite() {
            fail(format!("{}: non-finite determinant during root isolation", case.name));
        }

        let candidate = if f_left == 0.0 {
            Some(mu_left)
        } else if f_right == 0.0 {
            Some(mu_right)
        } else if signs_differ(f_left, f_right) {
            Some(refine_bracket(case, mu_left, mu_right, f_left))
        } else {
            None
        };

        if let Some(mu_root) = candidate {
            if mu_root > 0.0
                && roots_mu
                    .last()
                    .map_or(true, |previous| (mu_root - *previous).abs() > 2.5e-8)
            {
                roots_mu.push(mu_root);
            }
        }

        mu_left = mu_right;
        f_left = f_right;
    }

    if roots_mu.len() != case.modes {
        fail(format!(
            "{}: search found {} roots, expected {}; increase mu_max or provide a valid search domain",
            case.name,
            roots_mu.len(),
            case.modes
        ));
    }

    roots_mu.into_iter().map(|mu| mu * mu).collect()
}

fn square_integral(a: f64, b: f64, omega: f64, length: f64) -> f64 {
    let phase = omega * length;
    a * a * (length * 0.5 + (2.0 * phase).sin() / (4.0 * omega))
        + b * b * (length * 0.5 - (2.0 * phase).sin() / (4.0 * omega))
        + a * b * phase.sin().powi(2) / omega
}

fn linear_integral(a: f64, b: f64, omega: f64, length: f64) -> f64 {
    let phase = omega * length;
    a * phase.sin() / omega + b * (1.0 - phase.cos()) / omega
}

fn mode_for(case: &Case, index: usize, lambda: f64) -> Mode {
    let states = trace(case, lambda);
    let omega1 = (lambda / case.alpha1).sqrt();
    let omega2 = (lambda / case.alpha2).sqrt();
    let omega3 = (lambda / case.alpha3).sqrt();
    let b1 = states.left.q / (case.k1 * omega1);
    let b2 = states.i1_right.q / (case.k2 * omega2);
    let b3 = states.i2_right.q / (case.k3 * omega3);

    let mass = case.c1 * square_integral(states.left.phi, b1, omega1, case.l1)
        + case.c2 * square_integral(states.i1_right.phi, b2, omega2, case.l2)
        + case.c3 * square_integral(states.i2_right.phi, b3, omega3, case.l3)
        + case.b_left * states.left.phi.powi(2)
        + case.b_right * states.right.phi.powi(2)
        + case.s12 * states.i1_right.phi.powi(2)
        + case.s23 * states.i2_right.phi.powi(2);
    if !mass.is_finite() || mass <= 0.0 {
        fail(format!("{} mode {index}: invalid modal mass {mass}", case.name));
    }
    let scale = 1.0 / mass.sqrt();

    let heat_content = scale
        * (case.c1 * linear_integral(states.left.phi, b1, omega1, case.l1)
            + case.c2 * linear_integral(states.i1_right.phi, b2, omega2, case.l2)
            + case.c3 * linear_integral(states.i2_right.phi, b3, omega3, case.l3)
            + case.b_left * states.left.phi
            + case.b_right * states.right.phi
            + case.s12 * states.i1_right.phi
            + case.s23 * states.i2_right.phi);

    let delta_lambda = (1.0e-5 * lambda).max(1.0e-6);
    let f_lambda = (-determinant(case, lambda + 2.0 * delta_lambda)
        + 8.0 * determinant(case, lambda + delta_lambda)
        - 8.0 * determinant(case, lambda - delta_lambda)
        + determinant(case, lambda - 2.0 * delta_lambda))
        / (12.0 * delta_lambda);

    let delta_h = 1.0e-5;
    let mut plus_2h = case.clone();
    let mut plus_h = case.clone();
    let mut minus_h = case.clone();
    let mut minus_2h = case.clone();
    plus_2h.h_right += 2.0 * delta_h;
    plus_h.h_right += delta_h;
    minus_h.h_right -= delta_h;
    minus_2h.h_right -= 2.0 * delta_h;
    let f_h = (-determinant(&plus_2h, lambda)
        + 8.0 * determinant(&plus_h, lambda)
        - 8.0 * determinant(&minus_h, lambda)
        + determinant(&minus_2h, lambda))
        / (12.0 * delta_h);

    let delta_r = 1.0e-6;
    let mut plus_2r = case.clone();
    let mut plus_r = case.clone();
    let mut minus_r = case.clone();
    let mut minus_2r = case.clone();
    plus_2r.r12 += 2.0 * delta_r;
    plus_r.r12 += delta_r;
    minus_r.r12 -= delta_r;
    minus_2r.r12 -= 2.0 * delta_r;
    let f_r = (-determinant(&plus_2r, lambda)
        + 8.0 * determinant(&plus_r, lambda)
        - 8.0 * determinant(&minus_r, lambda)
        + determinant(&minus_2r, lambda))
        / (12.0 * delta_r);

    if !f_lambda.is_finite() || f_lambda.abs() < 1.0e-14 {
        fail(format!("{} mode {index}: singular sensitivity denominator", case.name));
    }
    let sensitivity_h_right = -f_h / f_lambda;
    let sensitivity_r12 = -f_r / f_lambda;

    let values = [
        lambda,
        scale,
        states.i1_left.phi * scale,
        states.i1_right.phi * scale,
        states.i2_left.phi * scale,
        states.i2_right.phi * scale,
        states.right.phi * scale,
        states.i1_left.q * scale,
        states.i1_right.q * scale,
        states.i2_left.q * scale,
        states.i2_right.q * scale,
        sensitivity_h_right,
        sensitivity_r12,
        heat_content,
    ];
    if values.iter().any(|value| !value.is_finite()) {
        fail(format!("{} mode {index}: non-finite result", case.name));
    }

    Mode {
        index,
        eigenvalue: lambda,
        left_amplitude: scale,
        interface1_left: states.i1_left.phi * scale,
        interface1_right: states.i1_right.phi * scale,
        interface2_left: states.i2_left.phi * scale,
        interface2_right: states.i2_right.phi * scale,
        right_amplitude: states.right.phi * scale,
        interface1_flux_left: states.i1_left.q * scale,
        interface1_flux_right: states.i1_right.q * scale,
        interface2_flux_left: states.i2_left.q * scale,
        interface2_flux_right: states.i2_right.q * scale,
        sensitivity_h_right,
        sensitivity_r12,
        modal_heat_content: heat_content,
    }
}

fn report(case: &Case) -> String {
    let roots = first_roots(case);
    let modes: Vec<Mode> = roots
        .iter()
        .enumerate()
        .map(|(index, &lambda)| mode_for(case, index + 1, lambda))
        .collect();

    let mut output = String::new();
    output.push_str("{\n");
    output.push_str(&format!("  \"case\": \"{}\",\n", case.name));
    output.push_str(&format!("  \"mode_count\": {},\n", case.modes));
    output.push_str("  \"modes\": [\n");
    for (position, mode) in modes.iter().enumerate() {
        output.push_str("    {\n");
        output.push_str(&format!("      \"index\": {},\n", mode.index));
        output.push_str(&format!("      \"eigenvalue\": {:.10},\n", mode.eigenvalue));
        output.push_str(&format!("      \"left_amplitude\": {:.10},\n", mode.left_amplitude));
        output.push_str(&format!("      \"interface1_left\": {:.10},\n", mode.interface1_left));
        output.push_str(&format!("      \"interface1_right\": {:.10},\n", mode.interface1_right));
        output.push_str(&format!("      \"interface2_left\": {:.10},\n", mode.interface2_left));
        output.push_str(&format!("      \"interface2_right\": {:.10},\n", mode.interface2_right));
        output.push_str(&format!("      \"right_amplitude\": {:.10},\n", mode.right_amplitude));
        output.push_str(&format!("      \"interface1_flux_left\": {:.10},\n", mode.interface1_flux_left));
        output.push_str(&format!("      \"interface1_flux_right\": {:.10},\n", mode.interface1_flux_right));
        output.push_str(&format!("      \"interface2_flux_left\": {:.10},\n", mode.interface2_flux_left));
        output.push_str(&format!("      \"interface2_flux_right\": {:.10},\n", mode.interface2_flux_right));
        output.push_str(&format!("      \"sensitivity_h_right\": {:.10},\n", mode.sensitivity_h_right));
        output.push_str(&format!("      \"sensitivity_R12\": {:.10},\n", mode.sensitivity_r12));
        output.push_str(&format!("      \"modal_heat_content\": {:.10}\n", mode.modal_heat_content));
        let comma = if position + 1 == modes.len() { "" } else { "," };
        output.push_str(&format!("    }}{comma}\n"));
    }
    output.push_str("  ]\n");
    output.push_str("}\n");
    output
}

fn lexical_absolute(path: &Path) -> PathBuf {
    let absolute = if path.is_absolute() {
        path.to_path_buf()
    } else {
        env::current_dir()
            .unwrap_or_else(|error| fail(format!("cannot read current directory: {error}")))
            .join(path)
    };
    let mut normalized = PathBuf::new();
    for component in absolute.components() {
        match component {
            Component::CurDir => {}
            Component::ParentDir => {
                normalized.pop();
            }
            other => normalized.push(other.as_os_str()),
        }
    }
    normalized
}

fn canonical_target(path: &Path) -> PathBuf {
    if let Ok(resolved) = fs::canonicalize(path) {
        return resolved;
    }

    let absolute = lexical_absolute(path);
    let mut unresolved: Vec<OsString> = Vec::new();
    let mut cursor = absolute.as_path();
    loop {
        if let Ok(mut resolved) = fs::canonicalize(cursor) {
            for component in unresolved.iter().rev() {
                resolved.push(component);
            }
            return resolved;
        }
        let Some(name) = cursor.file_name() else {
            return absolute;
        };
        unresolved.push(name.to_os_string());
        let Some(parent) = cursor.parent() else {
            return absolute;
        };
        cursor = parent;
    }
}

fn validate_path_separation(input_dir: &Path, output_dir: &Path) {
    let input = fs::canonicalize(input_dir)
        .unwrap_or_else(|error| fail(format!("cannot resolve {}: {error}", input_dir.display())));
    let output = canonical_target(output_dir);
    if output == input || input.starts_with(&output) || output.starts_with(&input) {
        fail("input and output paths must be distinct and neither may contain the other");
    }
}

fn reset_output_directory(path: &Path) {
    match fs::symlink_metadata(path) {
        Ok(metadata) => {
            if metadata.file_type().is_dir() && !metadata.file_type().is_symlink() {
                fs::remove_dir_all(path)
                    .unwrap_or_else(|error| fail(format!("cannot remove {}: {error}", path.display())));
            } else {
                fs::remove_file(path)
                    .unwrap_or_else(|error| fail(format!("cannot remove {}: {error}", path.display())));
            }
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
        Err(error) => fail(format!("cannot inspect {}: {error}", path.display())),
    }
    fs::create_dir_all(path)
        .unwrap_or_else(|error| fail(format!("cannot create {}: {error}", path.display())));
}

fn write_atomic(path: &Path, content: &str) {
    let temporary = path.with_extension("json.tmp");
    let mut file = fs::File::create(&temporary)
        .unwrap_or_else(|error| fail(format!("cannot create {}: {error}", temporary.display())));
    file.write_all(content.as_bytes())
        .unwrap_or_else(|error| fail(format!("cannot write {}: {error}", temporary.display())));
    file.sync_all()
        .unwrap_or_else(|error| fail(format!("cannot sync {}: {error}", temporary.display())));
    fs::rename(&temporary, path)
        .unwrap_or_else(|error| fail(format!("cannot replace {}: {error}", path.display())));
}

fn run(input_dir: &Path, output_dir: &Path) {
    if !input_dir.is_dir() {
        fail(format!("input directory does not exist: {}", input_dir.display()));
    }
    validate_path_separation(input_dir, output_dir);

    let mut paths: Vec<PathBuf> = fs::read_dir(input_dir)
        .unwrap_or_else(|error| fail(format!("cannot read {}: {error}", input_dir.display())))
        .map(|entry| entry.unwrap_or_else(|error| fail(format!("cannot read directory entry: {error}"))).path())
        .filter(|path| path.extension().and_then(|value| value.to_str()) == Some("case"))
        .collect();
    paths.sort();
    if paths.is_empty() {
        fail("input directory contains no .case files");
    }

    let mut cases = Vec::with_capacity(paths.len());
    let mut names = HashSet::new();
    for path in paths {
        let case = parse_case(&path);
        if !names.insert(case.name.clone()) {
            fail(format!("duplicate case name: {}", case.name));
        }
        cases.push(case);
    }

    let reports: Vec<(String, String)> = cases
        .iter()
        .map(|case| (case.name.clone(), report(case)))
        .collect();

    reset_output_directory(output_dir);
    for (name, content) in reports {
        let destination = output_dir.join(format!("{name}.json"));
        write_atomic(&destination, &content);
    }
}

fn main() {
    let (input_dir, output_dir) = parse_cli();
    run(&input_dir, &output_dir);
}
