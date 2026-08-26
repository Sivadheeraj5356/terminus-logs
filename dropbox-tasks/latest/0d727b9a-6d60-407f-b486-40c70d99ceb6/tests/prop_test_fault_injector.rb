# frozen_string_literal: true
require 'json'
require 'webrick'

# Verifier-only fault injection for property-test meta-checks.
# Loaded exclusively via RUBYOPT -r from the private verifier tree; never shipped under /app.
module PropTestFaultInjector
  def self.active_fault
    fault = ENV['PROP_TEST_FAULT']
    fault if fault.is_a?(String) && fault != 'none' && !fault.empty?
  end

  def self.apply!(server)
    case active_fault
    when 'unsigned_admin'
      apply_unsigned_admin(server)
    when 'intermittent_admin_leak'
      apply_intermittent_admin_leak(server)
    when 'broken_command'
      apply_broken_command(server)
    when 'broken_attempts'
      apply_broken_attempts(server)
    when 'open_moderator'
      apply_open_moderator(server)
    when 'accept_replay'
      apply_accept_replay(server)
    end
  end

  def self.json_response(res, body, status: 200)
    res.status = status
    res['Content-Type'] = 'application/json'
    res.body = JSON.generate(body)
  end

  def self.signed_admin?(req)
    req['x-admin-signature'] && req['x-timestamp'] && req['x-nonce']
  end

  def self.apply_unsigned_admin(server)
    server.mount_proc '/admin/debug-dump' do |_req, res|
      json_response(res, { debug: true, fault: 'unsigned_admin' })
    end
  end

  def self.apply_intermittent_admin_leak(server)
    counter = 0
    server.mount_proc '/admin/debug-dump' do |req, res|
      if signed_admin?(req)
        AdminRoutes.handle_debug_dump(req, res)
        next
      end
      counter += 1
      if counter > 10
        json_response(res, { debug: true, fault: 'intermittent_admin_leak' })
      else
        json_response(res, { error: 'forbidden' }, status: 403)
      end
    end
  end

  def self.apply_broken_command(server)
    server.mount_proc '/command' do |_req, res|
      res.status = 500
      res['Content-Type'] = 'application/json'
      res.body = '{}'
    end
  end

  def self.apply_broken_attempts(server)
    # Always report an evaluated attempt so concurrency tests see >>3 evaluations.
    server.mount_proc '/command' do |req, res|
      raw = req.body || ''
      begin
        body = JSON.parse(raw.empty? ? '{}' : raw)
      rescue JSON::ParserError
        json_response(res, { error: 'invalid JSON' }, status: 400)
        next
      end
      verb = body['verb'].to_s.strip
      if verb == 'attempt'
        json_response(res, { ok: false, reason: 'wrong_answer', attempts_remaining: 99 })
        next
      end
      GameRoutes.handle_command(req, res)
    end
  end

  def self.apply_open_moderator(server)
    # Accept moderator verbs without any signature check.
    server.mount_proc '/command' do |req, res|
      raw = req.body || ''
      begin
        body = JSON.parse(raw.empty? ? '{}' : raw)
      rescue JSON::ParserError
        json_response(res, { error: 'invalid JSON' }, status: 400)
        next
      end
      verb = body['verb'].to_s.strip
      if Dispatcher::MODERATOR_VERBS.include?(verb)
        json_response(res, { ok: true, action: verb, fault: 'open_moderator' })
        next
      end
      GameRoutes.handle_command(req, res)
    end
  end

  def self.apply_accept_replay(server)
    # Accept any request that presents admin headers, including nonce replays.
    server.mount_proc '/admin/debug-dump' do |req, res|
      if signed_admin?(req)
        json_response(res, {
          debug: true,
          settings: $settings.reject { |k, _| k == 'moderator_key' || k == 'admin_secret' },
          puzzle_state: $puzzle_engine.state,
          vault: $vault.status,
          sessions: $session_store.count
        })
      else
        json_response(res, { error: 'forbidden' }, status: 403)
      end
    end
  end

  def self.install_webrick_hook!
    return if @hook_installed

    WEBrick::HTTPServer.class_eval do
      alias_method :__prop_test_orig_start, :start unless method_defined?(:__prop_test_orig_start)

      def start
        PropTestFaultInjector.apply!(self)
        __prop_test_orig_start
      end
    end
    @hook_installed = true
  end
end

PropTestFaultInjector.install_webrick_hook!
