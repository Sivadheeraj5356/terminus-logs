defmodule HelixPipeline.Catalog.Client do
  @moduledoc """
  MySQL client for the Helix dependency catalog.
  """

  @doc """
  Open a connection to the catalog database using application config.
  Returns `{:ok, conn}` or `{:error, reason}`.
  """
  def connect do
    opts = Application.fetch_env!(:helix_pipeline, __MODULE__)
    MyXQL.start_link(opts)
  end

  @doc """
  Ping the catalog database. Returns `:ok` or `{:error, reason}`.
  """
  def ping do
    with {:ok, conn} <- connect(),
         {:ok, _result} <- MyXQL.query(conn, "SELECT 1") do
      GenServer.stop(conn)
      :ok
    else
      {:error, reason} -> {:error, reason}
    end
  end

  @doc """
  Run a parameterized query and return rows as maps with string keys.
  """
  def query(conn, sql, params \\ []) do
    case MyXQL.query(conn, sql, params) do
      {:ok, result} ->
        rows =
          Enum.map(result.rows, fn row ->
            result.columns
            |> Enum.zip(row)
            |> Map.new(fn {col, val} -> {col, normalize(val)} end)
          end)

        {:ok, rows}

      {:error, reason} ->
        {:error, reason}
    end
  end

  defp normalize(%Date{} = date), do: Date.to_iso8601(date)
  defp normalize(%DateTime{} = dt), do: DateTime.to_iso8601(dt)
  defp normalize(other), do: other
end
