# frozen_string_literal: true
# Package root: load path only. Drivers require leaf files directly.
module K9r
  ROOT = File.expand_path("..", __dir__)
end
$LOAD_PATH.unshift(File.join(K9r::ROOT)) unless $LOAD_PATH.include?(File.join(K9r::ROOT))
