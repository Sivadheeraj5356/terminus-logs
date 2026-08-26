defmodule HelixPipeline.Manifest.Loader do
  @moduledoc """
  Loads and merges Helix manifest files from the configured manifest directory.
  """

  alias HelixPipeline.Manifest.Parser

  @doc """
  Load services.yaml and toolchain.toml, returning a merged manifest map with keys:
  `:version`, `:dependencies`, `:toolchain`, and `:platform`.
  """
  def load(manifest_dir) do
    yaml_path = Path.join(manifest_dir, "services.yaml")
    toml_path = Path.join(manifest_dir, "toolchain.toml")

    yaml = Parser.parse_yaml(yaml_path)
    toml = Parser.parse_toml(toml_path)

    %{
      version: Map.fetch!(yaml, "version"),
      dependencies: Map.fetch!(yaml, "dependencies"),
      toolchain: Map.fetch!(toml, "toolchain"),
      platform: Map.fetch!(toml, "platform")
    }
  end
end
