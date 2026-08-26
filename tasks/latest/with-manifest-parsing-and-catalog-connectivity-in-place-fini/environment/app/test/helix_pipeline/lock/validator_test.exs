defmodule HelixPipeline.Lock.ValidatorTest do
  use ExUnit.Case, async: true

  alias HelixPipeline.Lock.Validator

  test "schema file exists" do
    assert File.exists?("/app/priv/schemas/lock.schema.json")
  end

  @tag :skip
  test "validates generated lock file" do
    # Exercised by the Python verifier after mix helix.lock runs.
    assert :ok = Validator.validate("/app/build/helix.lock.toml")
  end
end
