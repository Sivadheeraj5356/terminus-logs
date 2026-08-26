defmodule HelixPipeline.Lock.Builder do
  @moduledoc """
  Builds a deterministic helix.lock.toml from a parsed manifest and catalog data.
  """

  @doc """
  Build lock file contents as a UTF-8 string.
  """
  def build(manifest, catalog) do
    hash = manifest_hash(manifest)

    dep_sections =
      manifest.dependencies
      |> Enum.sort_by(& &1["name"])
      |> Enum.filter(fn dep -> Map.has_key?(catalog, dep["name"]) end)
      |> Enum.map(&render_dependency(&1, Map.fetch!(catalog, &1["name"])))
      |> Enum.join("\n\n")

    """
    [metadata]
    manifest_hash = "#{hash}"

    [toolchain]
    elixir = "#{manifest.toolchain["elixir"]}"
    otp = "#{manifest.toolchain["otp"]}"

    #{dep_sections}
    """
    |> String.trim()
    |> Kernel.<>("\n")
  end

  @doc """
  Write lock contents to `output_path`, creating parent directories as needed.
  """
  def write!(manifest, catalog, output_path) do
    contents = build(manifest, catalog)
    File.mkdir_p!(Path.dirname(output_path))
    File.write!(output_path, contents)
  end

  defp render_dependency(%{"name" => name, "pin" => pin}, catalog) do
    approval = catalog["approval"]
    status = approval["approval_status"]

    {version, source} =
      if status == "approved" do
        {approval["approved_version"], "catalog"}
      else
        {pin, "pin"}
      end

    constraint_lines =
      catalog["constraints"]
      |> Enum.sort_by(fn c -> {c["os"], c["arch"], c["min_version"], c["max_version"]} end)
      |> Enum.map(fn c ->
        """
        [[dependencies.#{name}.constraints]]
        os = "#{c["os"]}"
        arch = "#{c["arch"]}"
        min_version = "#{c["min_version"]}"
        max_version = "#{c["max_version"]}"
        """
        |> String.trim()
      end)
      |> Enum.join("\n\n")

    base =
      """
      [dependencies.#{name}]
      version = "#{version}"
      source = "#{source}"
      approval_status = "#{status}"
      """
      |> String.trim()

    if constraint_lines == "" do
      base <> "\nconstraints = []"
    else
      base <> "\n\n" <> constraint_lines
    end
  end

  defp manifest_hash(manifest) do
    dependencies =
      manifest.dependencies
      |> Enum.sort_by(& &1["name"])

    payload = %{
      "version" => manifest.version,
      "dependencies" => dependencies,
      "toolchain" => manifest.toolchain,
      "platform" => manifest.platform
    }

    payload
    |> sort_keys()
    |> Jason.encode!()
    |> then(&:crypto.hash(:sha256, &1))
    |> Base.encode16(case: :lower)
  end

  defp sort_keys(map) when is_map(map) do
    map
    |> Enum.sort_by(fn {k, _} -> to_string(k) end)
    |> Map.new(fn {k, v} -> {k, sort_keys(v)} end)
  end

  defp sort_keys(list) when is_list(list), do: Enum.map(list, &sort_keys/1)
  defp sort_keys(other), do: other
end
