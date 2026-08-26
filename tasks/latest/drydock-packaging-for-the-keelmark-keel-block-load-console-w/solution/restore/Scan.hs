{-# LANGUAGE CPP #-}
{-# LANGUAGE OverloadedStrings #-}

module Keelmark.Scan
  ( parseTensionEvents
  , peerEscalates
  , countNonBlankLines
  , windowFilter
  , dedupEvents
  ) where

import           Data.Aeson            (Value (..), decodeStrict)
import qualified Data.Aeson.KeyMap     as KM
import           Data.List             (foldl')
import qualified Data.Map.Strict       as Map
import           Data.Maybe            (mapMaybe)
import qualified Data.Text             as T
import           Data.Text.Encoding    (encodeUtf8)
import           Keelmark.Types        (TensionEvent (..))

-- One pass over the concatenated base+overlay stream. Accepted events
-- accumulate in order; under the gate-v2 stream profile a retract row removes
-- every earlier accepted event sharing its (ts, peer) and never counts as an
-- event itself. Returns the surviving events plus the number of retracted
-- events. The pre-migration tide profile predates overlay retraction and
-- passes retract rows through as unrecognized telemetry.
parseTensionEvents :: String -> ([TensionEvent], Int)
parseTensionEvents raw =
  let step (acc, dropped) line = case parseLine line of
        Just (Right ev) -> (acc ++ [ev], dropped)
#ifdef KEELMARK_GATE_V2
        Just (Left (ts, peer)) ->
          let (hit, keep) = span' (\e -> teTs e == ts && tePeer e == peer) acc
          in (keep, dropped + length hit)
#else
        Just (Left _) -> (acc, dropped)
#endif
        Nothing -> (acc, dropped)
  in foldl' step ([], 0) (lines raw)
  where
#ifdef KEELMARK_GATE_V2
    span' p xs = (filter p xs, filter (not . p) xs)
#endif

    parseLine line =
      let trimmed = T.unpack (T.strip (T.pack line))
      in if null trimmed
           then Nothing
           else case decodeStrict (encodeUtf8 (T.pack trimmed)) of
                  Just (Object o) -> do
                    ts <- lookupString o "ts"
                    peer <- lookupString o "peer"
                    kind <- lookupString o "kind"
                    case kind of
                      "retract" -> Just (Left (ts, peer))
                      "sample" -> do
                        kn <- lookupNumber o "kN"
                        Just (Right (TensionEvent ts kn peer kind))
                      "escalate" -> do
                        kn <- lookupNumber o "kN"
                        Just (Right (TensionEvent ts kn peer kind))
                      _ -> Nothing
                  _ -> Nothing

    lookupString o k = case KM.lookup k o of
      Just (String t) -> Just (T.unpack t)
      _               -> Nothing

    lookupNumber o k = case KM.lookup k o of
      Just (Number n) -> Just (fromRational (toRational n))
      _               -> Nothing

peerEscalates :: [TensionEvent] -> Bool
peerEscalates = any (\e -> teKind e == "escalate")

countNonBlankLines :: String -> Int
countNonBlankLines raw =
  length [ln | ln <- lines raw, not (T.null (T.strip (T.pack ln)))]

-- Keep events whose calendar date lies within the audit window, inclusive.
windowFilter :: String -> String -> [TensionEvent] -> [TensionEvent]
windowFilter start end =
  filter (\e -> let d = take 10 (teTs e) in d >= start && d <= end)

-- Collapse identical (ts, peer, kind) triples keeping the highest kN,
-- preserving first-appearance order of each triple.
dedupEvents :: [TensionEvent] -> [TensionEvent]
dedupEvents evs =
  let key e = (teTs e, tePeer e, teKind e)
      best = foldl' (\m e -> Map.insertWith max (key e) (teKN e) m) Map.empty evs
      go seen (e:rest)
        | key e `elem` seen = go seen rest
        | otherwise =
            e { teKN = best Map.! key e } : go (key e : seen) rest
      go _ [] = []
  in go [] evs
