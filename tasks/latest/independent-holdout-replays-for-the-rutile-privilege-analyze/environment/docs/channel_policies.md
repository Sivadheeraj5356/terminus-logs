# Channel policies

## Membership channel (`group`)

Only rows whose membership export marks them as currently active may contribute edges. Effective membership reachability must include hops implied by chaining active rows through intermediate principals.

## Assumption channel (`role`)

Role assumption exports declare direct delegation pairs. Effective assumption reachability includes hops implied by chaining delegation pairs through intermediate principals.

## Cluster binding channel (`k8s`)

Binding exports create subject→role edges. Aggregate exports declare role parenting; effective aggregate reachability includes hops implied by chaining aggregate rows. Binding subjects are not chained through aggregate parent paths; for example `svc-worker→cluster-admin` must not appear as a transitive k8s edge.

## Federation channel (`cloud`)

Federation exports contribute directed cloud-channel edges between declared endpoints.
