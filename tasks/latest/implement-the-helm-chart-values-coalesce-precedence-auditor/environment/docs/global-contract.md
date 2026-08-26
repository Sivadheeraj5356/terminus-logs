# Global contract

The `global` key is a map subtree in values documents.

When any applied layer includes `global`, helmvals deep-merges it into `values[<chartId>].global` for **each** chart in `active_charts` after that layer is applied to the relevant chart scope.

Global merges are independent per chart: each chart maintains its own `global` subtree, but all receive the same incoming `global` payload from a given layer.

Parent-only keys outside `global` are not copied to subcharts unless passed through the subchart values key.
