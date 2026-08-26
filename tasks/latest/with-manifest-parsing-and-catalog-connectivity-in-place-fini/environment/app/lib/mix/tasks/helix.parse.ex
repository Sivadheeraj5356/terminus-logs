defmodule Mix.Tasks.Helix.Parse do
  @moduledoc "Parse Helix manifests and verify catalog connectivity."
  use Mix.Task

  @shortdoc "Parse YAML/TOML manifests and write /app/build/parsed_manifest.json"

  alias HelixPipeline.{Catalog.Client, Manifest.Loader}

  @impl Mix.Task
  def run(_args) do
    Mix.Task.run("app.start")

    manifest_dir = Application.fetch_env!(:helix_pipeline, :manifest_dir)
    build_dir = Application.fetch_env!(:helix_pipeline, :build_dir)
    output_path = Path.join(build_dir, "parsed_manifest.json")

    manifest = Loader.load(manifest_dir)

    case Client.ping() do
      :ok ->
        :ok

      {:error, reason} ->
        Mix.raise("catalog ping failed: #{inspect(reason)}")
    end

    payload = %{
      "version" => manifest.version,
      "dependencies" => Enum.sort_by(manifest.dependencies, & &1["name"]),
      "toolchain" => manifest.toolchain,
      "platform" => manifest.platform
    }

    File.mkdir_p!(build_dir)
    File.write!(output_path, Jason.encode!(payload, pretty: true))
    Mix.shell().info("wrote #{output_path}")
  end
end
