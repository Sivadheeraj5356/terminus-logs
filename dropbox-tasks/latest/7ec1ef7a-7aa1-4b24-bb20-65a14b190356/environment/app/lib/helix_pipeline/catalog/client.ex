defmodule HelixPipeline.Catalog.Client do
  @moduledoc """
  MySQL client for the Helix dependency catalog.
  """

  @doc """
  Open a connection to the catalog database using application config.
  Returns `{:ok, conn}` or `{:error, reason}`.
  """
  def connect do
    raise "HelixPipeline.Catalog.Client.connect/0 is not implemented"
  end

  @doc """
  Ping the catalog database. Returns `:ok` or `{:error, reason}`.
  """
  def ping do
    raise "HelixPipeline.Catalog.Client.ping/0 is not implemented"
  end

  @doc """
  Run a parameterized query and return rows as maps with string keys.
  """
  def query(_conn, _sql, _params \\ []) do
    raise "HelixPipeline.Catalog.Client.query/3 is not implemented"
  end
end
