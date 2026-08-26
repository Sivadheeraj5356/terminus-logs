require 'digest'

# Manages the vault's locked/open state and validates the final combination.
class Vault
  def initialize(vault_def)
    @id       = vault_def['id']
    @expected = vault_def['combination_hash']
    @state    = vault_def['state'] || 'locked'
  end

  def locked?
    @state == 'locked'
  end

  def open?
    @state == 'open'
  end

  # Attempts to open the vault with the given combination string.
  def try_open(combination)
    given = Digest::MD5.hexdigest(combination.to_s.strip.downcase)
    if given == @expected
      @state = 'open'
      true
    else
      false
    end
  end

  # Directly forces the vault open — used only by the admin force-unlock route.
  def force_open!
    @state = 'open'
  end

  def status
    { id: @id, state: @state }
  end
end
