import Config

if config_env() == :prod do
  config :helix_pipeline, HelixPipeline.Catalog.Client,
    hostname: System.get_env("HELIX_DB_HOST", "127.0.0.1"),
    port: String.to_integer(System.get_env("HELIX_DB_PORT", "3306")),
    username: System.get_env("HELIX_DB_USER", "helix"),
    password: System.get_env("HELIX_DB_PASS", "helix"),
    database: System.get_env("HELIX_DB_NAME", "helix_catalog")
end
