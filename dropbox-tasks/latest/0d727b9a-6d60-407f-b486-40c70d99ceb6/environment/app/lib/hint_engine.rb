require 'yaml'

# Serves contextual hints from the room definition without revealing answers.
class HintEngine
  def initialize(room_def)
    @puzzles = room_def['puzzles'] || []
  end

  def hint_for(puzzle_id)
    puzzle = @puzzles.find { |p| p['id'] == puzzle_id }
    return nil unless puzzle

    # Each hint is the puzzle description — flavour only, not the answer.
    puzzle['description']&.strip
  end

  def available_puzzles
    @puzzles.map { |p| p['id'] }
  end
end
