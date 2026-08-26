require 'json'

module GameRoutes
  def self.json_response(res, body, status: 200)
    res.status = status
    res['Content-Type'] = 'application/json'
    res.body = JSON.generate(body)
  end

  def self.parse_body(req)
    JSON.parse(req.body || '{}')
  rescue JSON::ParserError
    nil
  end

  def self.handle_state(req, res)
    unless req.request_method == 'GET'
      return json_response(res, { error: 'method not allowed' }, status: 405)
    end

    state = $puzzle_engine.state
    state[:vault] = $vault.status
    json_response(res, state)
  end

  def self.handle_hint(req, res)
    unless req.request_method == 'GET'
      return json_response(res, { error: 'method not allowed' }, status: 405)
    end

    puzzle_id = req.query['puzzle_id']
    unless puzzle_id
      return json_response(res, { error: 'puzzle_id required' }, status: 400)
    end

    hint = $hint_engine.hint_for(puzzle_id)
    unless hint
      return json_response(res, { error: 'unknown puzzle' }, status: 404)
    end

    prefix = $messages.dig('messages', 'hint_prefix') || ''
    json_response(res, { puzzle_id: puzzle_id, hint: prefix + hint })
  end

  def self.handle_new_session(req, res)
    unless req.request_method == 'POST'
      return json_response(res, { error: 'method not allowed' }, status: 405)
    end

    session_id = $session_store.create
    json_response(res, { session_id: session_id })
  end

  def self.handle_command(req, res)
    unless req.request_method == 'POST'
      return json_response(res, { error: 'method not allowed' }, status: 405)
    end

    raw_body = req.body || ''
    body     = parse_body(req)
    unless body
      return json_response(res, { error: 'invalid JSON' }, status: 400)
    end

    verb    = body['verb'].to_s.strip
    payload = body['payload'] || {}

    # Stateful verbs require a valid session token.
    if %w[attempt unlock].include?(verb)
      session_token = req['x-session-token']
      unless session_token && $session_store.fetch(session_token)
        return json_response(res, { error: 'invalid or missing session token' }, status: 401)
      end
    end

    result = $dispatcher.dispatch(verb, payload, req, raw_body)
    if result[:error]
      return json_response(res, result, status: result[:status] || 400)
    end

    case result[:action]
    when 'attempt'
      target = result[:target]
      data   = result[:data]
      attempt_result = $puzzle_engine.attempt(target, data)
      json_response(res, attempt_result)
    when 'examine', 'inspect'
      json_response(res, { ok: true, description: $room_def['room']['description'] })
    when 'unlock'
      if $puzzle_engine.all_puzzles_solved?
        ok = $vault.try_open(result[:data].to_s)
        json_response(res, { ok: ok, vault: $vault.status })
      else
        json_response(res, { ok: false, reason: 'puzzles incomplete' }, status: 422)
      end
    else
      json_response(res, { ok: true, result: result })
    end
  end
end
