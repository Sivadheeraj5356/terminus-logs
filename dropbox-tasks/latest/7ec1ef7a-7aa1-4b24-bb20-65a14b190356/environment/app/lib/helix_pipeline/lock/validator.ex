defmodule HelixPipeline.Lock.Validator do
  @moduledoc """
  Validates helix.lock.toml against the JSON schema at priv/schemas/lock.schema.json.
  """

  @doc """
  Validate lock file at `path`. Returns `:ok` or `{:error, messages}`.
  """
  def validate(path) do
    schema_path = Application.fetch_env!(:helix_pipeline, :lock_schema_path)
    schema = schema_path |> File.read!() |> Jason.decode!()
    lock = path |> File.read!() |> Toml.decode!()

    case ExJsonSchema.Validator.validate(schema, lock) do
      :ok -> :ok
      {:error, errors} -> {:error, Enum.map(errors, &Exception.message/1)}
    end
  end
end
