require 'json'
require 'openssl'

module AdminRoutes
  def self.json_response(res, body, status: 200)
    res.status = status
    res['Content-Type'] = 'application/json'
    res.body = JSON.generate(body)
  end

  def self.forbidden_unless_signed(req, res)
    ts  = req['x-timestamp']
    sig = req['x-admin-signature']
    nonce = req['x-nonce']

    unless ts && sig && nonce
      res.status = 403
      res.body = '{"error":"forbidden"}'
      return true
    end

    ts_i = ts.to_i
    now  = Time.now.to_i
    if (ts_i - now).abs > 60
      res.status = 403
      res.body = '{"error":"forbidden"}'
      return true
    end

    secret = $settings['admin_secret'] || ''
    expected_sig = OpenSSL::HMAC.hexdigest('SHA1', secret, "#{req.path}:#{ts}:#{nonce}")

    unless sig == expected_sig
      res.status = 403
      res.body = '{"error":"forbidden"}'
      return true
    end

    unless $nonce_store.record!(nonce)
      res.status = 403
      res.body = '{"error":"forbidden","reason":"replay"}'
      return true
    end

    false
  end

  def self.handle_debug_dump(req, res)
    return if forbidden_unless_signed(req, res)
    unless req.request_method == 'POST'
      return json_response(res, { error: 'method not allowed' }, status: 405)
    end

    json_response(res, {
      debug: true,
      settings: $settings.reject { |k, _| k == 'moderator_key' || k == 'admin_secret' },
      puzzle_state: $puzzle_engine.state,
      vault: $vault.status,
      sessions: $session_store.count
    })
  end

  def self.handle_force_unlock(req, res)
    return if forbidden_unless_signed(req, res)
    unless req.request_method == 'POST'
      return json_response(res, { error: 'method not allowed' }, status: 405)
    end

    $vault.force_open!
    json_response(res, { ok: true, message: 'vault force-opened', vault: $vault.status })
  end
end
