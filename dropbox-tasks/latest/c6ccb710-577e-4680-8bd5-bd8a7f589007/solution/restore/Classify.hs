module Keelmark.Classify
  ( classifyBlock
  , effTenths
  , loadIndex
  , padTensionTs
  , dominantPeer
  , selectLastEvent
  ) where

import           Data.List       (maximumBy, sortBy)
import           Data.Ord        (comparing)
import qualified Data.Map.Strict as Map
import           Keelmark.Types  (TensionEvent (..))

-- Calibrated tension in tenths of a kN, rounded half-up to one decimal.
effTenths :: Double -> Double -> Integer
effTenths maxKn gain = floor (maxKn * gain * 10 + 0.5)

classifyBlock :: Double -> Double -> Integer -> Bool -> String
classifyBlock warnKn critKn effT hasEsc
  | effVal >= critKn || hasEsc = "CRITICAL"
  | effVal >= warnKn           = "WARN"
  | otherwise                  = "STABLE"
  where
    effVal = fromIntegral effT / 10

-- load_index = floor((eff_max_kN * 1000 + sample_count * 7) / max(1, rated)).
-- eff_max_kN * 1000 equals effTenths * 100 exactly, so this stays in integers.
loadIndex :: Integer -> Int -> Int -> Integer
loadIndex effT sampleCount rated =
  (effT * 100 + fromIntegral sampleCount * 7) `div` fromIntegral (max 1 rated)

-- Pad hour and second to two digits; leave minute unpadded.
padTensionTs :: String -> String
padTensionTs ts =
  case break (== 'T') ts of
    (date, 'T':rest) ->
      case span (/= 'Z') rest of
        (hms, zs) -> date ++ "T" ++ padHMS hms ++ zs
    _ -> ts
  where
    padHMS hms =
      case splitOn ':' hms of
        [h, m, s] -> pad2 h ++ ":" ++ m ++ ":" ++ pad2 s
        _         -> hms
    pad2 xs = if length xs == 1 then '0' : xs else xs
    splitOn _ [] = [""]
    splitOn d xs =
      let (a, b) = break (== d) xs
      in a : case b of
               []     -> []
               (_:ys) -> splitOn d ys

dominantPeer :: [TensionEvent] -> String
dominantPeer evs =
  let counts = Map.fromListWith (+) [(tePeer e, 1 :: Int) | e <- evs]
      ranked = sortBy peerOrder (Map.toList counts)
  in case ranked of
       ((p, _):_) -> p
       []         -> ""
  where
    peerOrder (p1, c1) (p2, c2) =
      compare c2 c1 <> compare p2 p1

selectLastEvent :: [TensionEvent] -> TensionEvent
selectLastEvent evs =
  maximumBy (comparing teTs) evs
