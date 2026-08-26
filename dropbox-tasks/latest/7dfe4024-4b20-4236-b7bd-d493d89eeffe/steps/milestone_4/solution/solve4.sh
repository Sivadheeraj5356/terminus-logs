#!/bin/bash
set -euo pipefail

# Insert validate_config and generate_debug_report before the class closing end
cat > /tmp/add_methods.rb << 'RUBY_SCRIPT'
code = File.read('/app/lib/spectral_analyzer.rb')

extra = <<~'METHODS'

  def validate_config
    ranges = {
      sensor_frequency_hz: 100..10000,
      sample_duration_sec: 0.1..60.0,
      damping_coefficient: 0.0..1.0,
      natural_frequency_hz: 1..1000
    }
    errors = []
    ranges.each do |key, range|
      val = @params[key]
      errors << "#{key} (#{val}) outside range #{range}" if val && !range.include?(val)
    end
    # Nyquist-Shannon constraint: natural frequency must not exceed
    # half the sample rate to avoid aliasing.
    sr = @params[:sensor_frequency_hz]
    nf = @params[:natural_frequency_hz]
    if sr && nf && nf > sr / 2.0
      errors << "natural_frequency_hz (#{nf}) exceeds Nyquist limit (#{sr / 2.0} Hz)"
    end
    if @params[:sensor_id] && !@params[:sensor_id].match?(/^ACCEL-\d{3}$/)
      errors << "sensor_id (#{@params[:sensor_id]}) must match ACCEL-XXX"
    end
    { valid: errors.empty?, errors: errors }
  end

  def generate_debug_report(data = nil)
    report = {
      parameters: @params,
      validation: validate_config,
      timestamp: Time.now.utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    }
    report[:simulation_data] = data if data
    File.write('/app/debug_report.json', JSON.pretty_generate(report))
    report
  end
METHODS

# Insert extra methods before the last line (which is the class closing 'end')
lines = code.lines
last_end_idx = lines.rindex { |l| l.strip == 'end' }
lines.insert(last_end_idx, extra)
File.write('/app/lib/spectral_analyzer.rb', lines.join)
RUBY_SCRIPT

ruby /tmp/add_methods.rb

# Create validation spec doc
cat > /app/docs/validation_spec.md << 'DOC'
# Configuration Validation

Parameters loaded from Containerfile are validated against these ranges:

- `sensor_frequency_hz`: 100–10000 Hz
- `sample_duration_sec`: 0.1–60.0 s
- `damping_coefficient`: 0.0–1.0 (dimensionless)
- `natural_frequency_hz`: 1–1000 Hz
- `sensor_id`: string matching `ACCEL-\d{3}`

## Cross-parameter constraints

- **Nyquist criterion**: `natural_frequency_hz` must not exceed
  `sensor_frequency_hz / 2`. Violating this would alias the signal.
DOC
