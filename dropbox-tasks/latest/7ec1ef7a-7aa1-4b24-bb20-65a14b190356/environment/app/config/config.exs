import Config

config :helix_pipeline,
  manifest_dir: "/app/priv/manifests",
  build_dir: "/app/build",
  lock_schema_path: "/app/priv/schemas/lock.schema.json"

config :helix_pipeline, HelixPipeline.Catalog.Client,
  hostname: "127.0.0.1",
  port: 3306,
  username: "helix",
  password: "helix",
  database: "helix_catalog"
