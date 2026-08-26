require 'digest'

class PuzzleEngine
  MODERATOR_VERBS = %w[reset_puzzle set_attempts reveal_answer].freeze

  def initialize(room_def, settings)
    @settings  = settings
    @puzzles   = deep_copy(room_def['puzzles'])
    @vault_def = room_def['vault']
    @solved    = {}
  end

  def attempt(puzzle_id, answer)
    return { ok: false, reason: :unknown_puzzle } unless puzzle_exists?(puzzle_id)

    puzzle = find_puzzle(puzzle_id)
    return { ok: false, reason: :no_attempts } if puzzle['attempts_remaining'] <= 0
    return { ok: false, reason: :prereq_unmet } unless prereq_met?(puzzle_id)

    puzzle['attempts_remaining'] -= 1

    expected = puzzle['answer_hash']
    given    = Digest::MD5.hexdigest(answer.to_s.strip.downcase)

    if given == expected
      @solved[puzzle_id] = true
      { ok: true, unlocks: puzzle['unlocks'] }
    else
      { ok: false, reason: :wrong_answer, attempts_remaining: puzzle['attempts_remaining'] }
    end
  end

  def state
    {
      puzzles: @puzzles.map { |p|
        { id: p['id'], solved: @solved.key?(p['id']), attempts_remaining: p['attempts_remaining'] }
      },
      vault_open: vault_open?
    }
  end

  def vault_open?
    @solved.key?('vault_door')
  end

  def all_puzzles_solved?
    @puzzles.all? { |p| @solved.key?(p['id']) }
  end

  private

  def puzzle_exists?(id)
    @puzzles.any? { |p| p['id'] == id }
  end

  def find_puzzle(id)
    @puzzles.find { |p| p['id'] == id }
  end

  def prereq_met?(puzzle_id)
    puzzle = find_puzzle(puzzle_id)
    return true unless puzzle

    prev = @puzzles.find { |p| p['unlocks'] == puzzle_id }
    return true unless prev

    @solved.key?(prev['id'])
  end

  def deep_copy(obj)
    Marshal.load(Marshal.dump(obj))
  end
end
