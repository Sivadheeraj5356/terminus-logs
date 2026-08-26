#!/usr/bin/env elixir
Mix.install([
  {:toml, "~> 0.7"},
  {:jason, "~> 1.4"},
  {:ex_json_schema, "~> 0.10"}
])

[lock_path, schema_path] = System.argv()

lock = lock_path |> File.read!() |> Toml.decode!()
schema = schema_path |> File.read!() |> Jason.decode!()

case ExJsonSchema.Validator.validate(schema, lock) do
  :ok ->
    IO.puts("valid")
    System.halt(0)

  {:error, errors} ->
    Enum.each(errors, fn err -> IO.puts(Exception.message(err)) end)
    System.halt(1)
end
