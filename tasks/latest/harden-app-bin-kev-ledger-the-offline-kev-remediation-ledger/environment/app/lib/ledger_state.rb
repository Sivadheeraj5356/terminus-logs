require 'digest'
require 'json'

module LedgerState
  module_function

  def sha256_bytes(bytes)
    Digest::SHA256.hexdigest(bytes)
  end

  def file_sha256(path)
    Digest::SHA256.file(path).hexdigest
  end

  def load_json(path)
    JSON.parse(File.read(path))
  end
end
