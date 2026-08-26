# Salt pond field topology

Four polygon arms share one diversion controller block.
Wind octants map through sector tables into lane advance targets for the numerical model.

Lane snapshots in `lane.db` carry both a physical packing sequence (`row_id`) and a display label (`arm_label`). Report `arms` arrays and daily survey vertices follow the packing sequence; display labels may be remapped independently in the field book.
