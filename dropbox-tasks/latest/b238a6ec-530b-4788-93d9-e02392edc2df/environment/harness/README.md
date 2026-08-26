# Sample schedules

Each seed script in this directory replays one schedule across a small group and
shows whether every acknowledged operation survived, whether an operation no
client ever submitted was accepted, and whether the group kept committing.

Run them with:

    bash /app/smoke.sh

Each seed file is a line-oriented script. A `mode` line names the schedule and a
`nodes` line sets the group size:

    mode handover
    nodes 5

The bundled seeds run a steady primary, a clean handover to a new primary, a
minority partition, a schedule in which the transport hands the group a message
that no replica sent (tagged under a key that is not the cluster key and carrying
an operation no client submitted), a schedule that stops and brings back a
replica, a schedule that replays a genuine message the transport captured, a
schedule that stops and brings back several replicas and then lets the transport
resurface acknowledgements those replicas sent in an earlier life, a schedule in
which one replica stops twice and the transport resurfaces the answers it was
given while catching up the first time, and a schedule that reorders, duplicates,
and transiently partitions traffic. These seeds are only examples: the group must
hold its guarantees on schedules well beyond them, under the same fault model.
