defmodule HelixPipeline.Manifest.Parser do
  @moduledoc """
  Parses Helix YAML and TOML manifest files into a normalized map.
  """

  @doc """
  Parse a YAML manifest file. Returns a map with string keys.
  """
  def parse_yaml(_path) do
    raise "HelixPipeline.Manifest.Parser.parse_yaml/1 is not implemented"
  end

  @doc """
  Parse a TOML manifest file. Returns a map with string keys.
  """
  def parse_toml(_path) do
    raise "HelixPipeline.Manifest.Parser.parse_toml/1 is not implemented"
  end
end
