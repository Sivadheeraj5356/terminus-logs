# frozen_string_literal: true

require_relative "../util/digest"
require_relative "../util/toml_loader"
require_relative "../m7k/step_mux"
require_relative "../r3p/cap_fold"
require_relative "../r3p/gen_cursor"
require_relative "../w9n/revert_arm"
require_relative "../tools/row_fmt"
require_relative "../tools/summary_mux"
require_relative "witness_bridge"

module Engine
  module Pipeline
    PAIRS = [%w[bind bind_echo], %w[upper upper_echo], %w[worker worker_echo]].freeze

    module_function

    def build_rows(env_root, opts = {})
      ladder = Util::TomlLoader.load(File.join(env_root, "data", "ladder.toml"))
      channel = Util::TomlLoader.load(File.join(env_root, "data", "channel.toml"))
      prim_ids = File.read(File.join(env_root, "docs", "prim_ids.txt")).strip.split(",")

      state = { tree: channel["seed"], gen: 0, gen_prev: 0, activated: false, published: 0 }
      hook = opts[:hook] || "run"
      apply_hook!(state, channel, hook, opts[:resume])

      rows = prim_ids.map do |unit_id|
        steps = ladder.dig("units", unit_id, "steps") || []
        build_row(unit_id, steps, state, hook)
      end

      rows = apply_ord_variant(rows, env_root, opts[:ord]) if opts[:ord]
      finalize_rc!(rows, hook, env_root)

      witness_path = File.join(env_root, "data", "byte_log_snapshot.json")
      Tools::RowFmt.emit_rows(rows, witness_path)
    end

    def apply_hook!(state, channel, hook, resume)
      case hook
      when "run_a"
        state[:gen] = 1
        state[:gen_prev] = 1
        state[:activated] = false
        state[:activated] = true if resume && resume > 0
      when "run_b"
        R3p::GenCursor.bump(state)
        old_tree = state[:tree]
        state[:tree] = channel["seed"] ^ 0xFF
        W9n::RevertArm.fn_w9(state, old_tree, channel["seed"])
        state[:activated] = false
      else
        state[:activated] = true
      end
    end

    def build_row(unit_id, steps, state, hook)
      mux_acc = 0
      prev_family = 0
      ctx = { activated: state[:activated], published: state[:published] }

      steps.each do |step_ix, family_ix|
        part = M7k::StepMux.fn_m7(step_ix, family_ix, prev_family)
        mux_acc = (mux_acc ^ part) & ((1 << 64) - 1)
        stamp_a = (state[:tree] & 0xFFFF) ^ step_ix
        stamp_b = (state[:published] & 0xFFFF) ^ family_ix
        R3p::CapFold.fn_r3(ctx, stamp_a, stamp_b)
        prev_family = family_ix
      end

      facet = Util::DigestUtil.facet_hex(
        steps.last&.first || 0,
        steps.last&.last || 0,
        prev_family,
        mux_acc
      )

      {
        unit_id: unit_id,
        bind_rc: 0,
        lock_rc: 0,
        unit_rc: 0,
        drift_code: 0,
        facet_hex: facet,
        _hook: hook,
        _ctx: ctx,
        _state: state
      }
    end

    def finalize_rc!(rows, hook, env_root)
      pair_ok = PAIRS.all? do |a, b|
        ra = rows.find { |r| r[:unit_id] == a }
        rb = rows.find { |r| r[:unit_id] == b }
        ra && rb && ra[:facet_hex] == rb[:facet_hex]
      end

      lock_ok = hook == "run" || rows.all? do |r|
        pub = r[:_ctx][:published]
        pub.nil? || pub == 0 || r[:_state][:activated]
      end
      unit_ok = hook == "run" || hook == "run_a" || rows.all? { |r| r[:_state][:gen] <= r[:_state][:gen_prev] }

      witness_path = File.join(env_root, "data", "byte_log_snapshot.json")
      witness_ok = Engine::WitnessBridge.witness_ok?(witness_path, rows)

      rows.each do |row|
        coherent = pair_ok && lock_ok && unit_ok && witness_ok
        row[:bind_rc] = pair_ok ? 1 : 0
        row[:lock_rc] = (lock_ok && witness_ok) ? 1 : 0
        row[:unit_rc] = unit_ok ? 1 : 0
        row[:drift_code] = coherent ? 0 : (row[:unit_id].sum % 7)
        row.delete(:_hook)
        row.delete(:_ctx)
        row.delete(:_state)
      end
    end

    def apply_ord_variant(rows, env_root, ord_key)
      idx = ord_key.split(":").last.to_i
      ord = Util::TomlLoader.load(File.join(env_root, "data", "ord_table.toml"))
      perms = ord["perm"] || []
      entry = perms[idx]
      swap = entry["swap"]
      a_id, b_id = swap
      a_row = rows.find { |r| r[:unit_id] == a_id }
      b_row = rows.find { |r| r[:unit_id] == b_id }
      return rows unless a_row && b_row && a_row[:facet_hex] == b_row[:facet_hex]

      rows
    end
  end
end
