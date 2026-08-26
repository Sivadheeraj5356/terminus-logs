# Operators

## Workspace build

`/app/environment/scripts/build_workspace.sh`

## Matrix driver

`ruby environment/qcl/drive_qcl.rb --matrix-all`

## Recovery after destructive cleanup

Run `ruby -e "require_relative 'environment/f5/scratch_arena'; F5::ScratchArena.clear!"` then rerun the matrix driver command.
