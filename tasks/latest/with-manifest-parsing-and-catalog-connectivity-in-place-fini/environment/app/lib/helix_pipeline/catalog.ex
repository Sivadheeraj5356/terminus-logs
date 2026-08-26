defmodule HelixPipeline.Catalog do
  @moduledoc """
  Catalog access helpers built on top of `HelixPipeline.Catalog.Queries`.
  """

  alias HelixPipeline.Catalog.{Client, Queries}

  @doc """
  Connect, call `Queries.fetch_enriched/4`, and disconnect.
  """
  def fetch_enriched!(names, os, arch) do
    {:ok, conn} = Client.connect()

    try do
      Queries.fetch_enriched(conn, names, os, arch)
    after
      GenServer.stop(conn)
    end
  end
end
