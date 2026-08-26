# Extension peer closure

After direct importer bindings are chosen, apply `/app/config/extensions.json`.
For every sealed package name matching an extension `whenPackage`, add each
name in `peerRequires` to the sealed package set (looked up in catalog
packages). Extension peers are part of the seal even when no importer lists
them directly.

Plan-graph `peers` is the sorted list of package names pulled in solely by
extensions (not direct importer targets). Store payloads for every sealed
package include a sorted `peers` array listing extension peers required by
that package (empty when none).
