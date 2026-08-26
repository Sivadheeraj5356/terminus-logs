defmodule Mix.Tasks.Helix.Lock do
  @moduledoc "Build and validate helix.lock.toml from manifest + catalog."
  use Mix.Task

  @shortdoc "Emit /app/build/helix.lock.toml from parsed manifest and catalog"

  alias HelixPipeline.{Catalog, Lock.Builder, Lock.Validator, Manifest.Loader}

  @impl Mix.Task
  def run(_args) do
    Mix.Task.run("app.start")

    manifest_dir = Application.fetch_env!(:helix_pipeline, :manifest_dir)
    build_dir = Application.fetch_env!(:helix_pipeline, :build_dir)
    lock_path = Path.join(build_dir, "helix.lock.toml")

    manifest = Loader.load(manifest_dir)
    os = manifest.platform["os"]
    arch = manifest.platform["arch"]

    names =
      manifest.dependencies
      |> Enum.map(fn dep -> dep["name"] end)

    catalog = Catalog.fetch_enriched!(names, os, arch)
    Builder.write!(manifest, catalog, lock_path)

    case Validator.validate(lock_path) do
      :ok ->
        Mix.shell().info("wrote #{lock_path}")

      {:error, errors} ->
        Mix.raise("lock validation failed: #{Enum.join(errors, "; ")}")
    end
  end
end
