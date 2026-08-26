require 'json'

class Dispatcher
  MODERATOR_VERBS = %w[reset_puzzle set_attempts reveal_answer grant_hint_token].freeze
  GAME_VERBS      = %w[examine unlock attempt hint use inspect].freeze

  def initialize(settings)
    @settings = settings
  end

  def dispatch(verb, payload, req = nil, raw_body = '')
    return { error: 'unknown verb', status: 400 } unless valid_verb?(verb)

    if req && $rate_limiter
      ip = req.peeraddr[3] rescue '0.0.0.0'
      unless $rate_limiter.allow?(ip)
        return { error: 'rate limit exceeded', status: 429 }
      end
    end

    if moderator_verb?(verb)
      handle_moderator(verb, payload)
    else
      handle_game(verb, payload)
    end
  end

  private

  def valid_verb?(verb)
    MODERATOR_VERBS.include?(verb) || GAME_VERBS.include?(verb)
  end

  def moderator_verb?(verb)
    MODERATOR_VERBS.include?(verb)
  end

  def handle_moderator(verb, payload)
    case verb
    when 'reset_puzzle'
      { action: 'reset_puzzle', target: payload['puzzle_id'] }
    when 'set_attempts'
      { action: 'set_attempts', target: payload['puzzle_id'], value: payload['attempts'] }
    when 'reveal_answer'
      { action: 'reveal_answer', target: payload['puzzle_id'] }
    when 'grant_hint_token'
      { action: 'grant_hint_token', target: payload['session_id'] }
    end
  end

  def handle_game(verb, payload)
    { action: verb, target: payload['target'], data: payload['data'] }
  end
end
