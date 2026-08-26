defmodule HelixPipeline.Manifest.Parser do
  @moduledoc """
  Parses Helix YAML and TOML manifest files into a normalized map.
  """

  @doc """
  Parse a YAML manifest file. Returns a map with string keys.
  """
  def parse_yaml(path) do
    path
    |> File.read!()
    |> YamlElixir.read_from_string!()
    |> stringify_keys()
  end

  @doc """
  Parse a TOML manifest file. Returns a map with string keys.
  """
  def parse_toml(path) do
    path
    |> File.read!()
    |> Toml.decode!()
    |> stringify_keys()
  end

  defp stringify_keys(%{} = map) do
    Map.new(map, fn {k, v} -> {to_string(k), stringify_keys(v)} end)
  end

  defp stringify_keys(list) when is_list(list), do: Enum.map(list, &stringify_keys/1)
  defp stringify_keys(other), do: other
end
