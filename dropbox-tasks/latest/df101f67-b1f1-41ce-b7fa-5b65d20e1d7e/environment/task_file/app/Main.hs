module Main where

import System.Environment (getArgs)
import System.Exit (die)

main :: IO ()
main = do
  args <- getArgs
  case args of
    ["--root", _, "--out-dir", _] ->
      die "planner not implemented"
    _ ->
      die "usage: harborlane-planner --root ROOT --out-dir OUT_DIR"
