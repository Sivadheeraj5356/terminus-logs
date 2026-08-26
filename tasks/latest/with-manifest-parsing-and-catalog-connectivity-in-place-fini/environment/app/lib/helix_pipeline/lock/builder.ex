defmodule HelixPipeline.Lock.Builder do
  @moduledoc false

  @doc false
  def build(_manifest, _catalog) do
    raise "HelixPipeline.Lock.Builder.build/2 is not implemented"
  end

  @doc """
  Write lock contents to `output_path`, creating parent directories as needed.
  """
  def write!(manifest, catalog, output_path) do
    contents = build(manifest, catalog)
    File.mkdir_p!(Path.dirname(output_path))
    File.write!(output_path, contents)
  end
end
