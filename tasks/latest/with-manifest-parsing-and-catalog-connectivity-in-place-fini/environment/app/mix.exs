defmodule HelixPipeline.MixProject do
  use Mix.Project

  def project do
    [
      app: :helix_pipeline,
      version: "0.1.0",
      elixir: "~> 1.14",
      start_permanent: Mix.env() == :prod,
      deps: deps()
    ]
  end

  def application do
    [
      extra_applications: [:logger]
    ]
  end

  defp deps do
    [
      {:yaml_elixir, "~> 2.9"},
      {:toml, "~> 0.7"},
      {:myxql, "~> 0.7"},
      {:jason, "~> 1.4"},
      {:ex_json_schema, "~> 0.10"}
    ]
  end
end
