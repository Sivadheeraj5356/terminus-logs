defmodule HelixPipeline.Catalog.Queries do
  @moduledoc """
  Catalog queries joining dependency approvals with platform constraints.
  """

  alias HelixPipeline.Catalog.Client

  @doc """
  For each dependency name in `names`, fetch approval rows and matching platform
  constraints for the given `os` and `arch`.
  """
  def fetch_enriched(conn, names, os, arch) do
    names = Enum.uniq(names)

    approvals =
      if names == [] do
        %{}
      else
        placeholders = Enum.map_join(1..length(names), ", ", fn _ -> "?" end)

        {:ok, rows} =
          Client.query(
            conn,
            """
            SELECT package_name, approved_version, approval_status
            FROM dependency_approvals
            WHERE package_name IN (#{placeholders})
            """,
            names
          )

        Map.new(rows, fn row -> {row["package_name"], row} end)
      end

    constraints =
      if names == [] do
        %{}
      else
        placeholders = Enum.map_join(1..length(names), ", ", fn _ -> "?" end)

        {:ok, rows} =
          Client.query(
            conn,
            """
            SELECT package_name, os, arch, min_version, max_version
            FROM platform_constraints
            WHERE package_name IN (#{placeholders})
              AND os = ?
              AND arch = ?
            ORDER BY package_name, os, arch
            """,
            names ++ [os, arch]
          )

        Enum.group_by(rows, & &1["package_name"])
      end

    names
    |> Enum.sort()
    |> Enum.reduce(%{}, fn name, acc ->
      case Map.get(approvals, name) do
        nil ->
          acc

        approval ->
          Map.put(acc, name, %{
            "approval" => approval,
            "constraints" => Map.get(constraints, name, [])
          })
      end
    end)
  end
end
