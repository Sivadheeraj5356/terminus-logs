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
import           Data.Maybe            (mapMaybe)
import qualified Data.Text             as T
import           Data.Text.Encoding    (encodeUtf8)
import           Keelmark.Types        (TensionEvent (..))

-- Tide-era stream scan. Load-cell rows arrive as sample or escalate
-- telemetry; anything else on the wire is unrecognized noise and never
-- becomes an event. The Int in the result is reserved by the tide sheet
-- and always reads zero.
parseTensionEvents :: String -> ([TensionEvent], Int)
parseTensionEvents raw = (mapMaybe parseLine (lines raw), 0)
  where
    parseLine line =
      let trimmed = T.unpack (T.strip (T.pack line))
      in if null trimmed
           then Nothing
           else case decodeStrict (encodeUtf8 (T.pack trimmed)) of
                  Just (Object o) -> do
                    ts <- lookupString o "ts"
                    peer <- lookupString o "peer"
                    kind <- lookupString o "kind"
                    kn <- lookupNumber o "kN"
                    if kind == "sample" || kind == "escalate"
                      then Just (TensionEvent ts kn peer kind)
                      else Nothing
                  _ -> Nothing

    lookupString o k = case KM.lookup k o of
      Just (String t) -> Just (T.unpack t)
      _               -> Nothing

    -- Tide load-cell firmware occasionally quotes kN; accept it either way.
    lookupNumber o k = case KM.lookup k o of
      Just (Number n) -> Just (fromRational (toRational n))
      Just (String t) -> case reads (T.unpack t) of
                           [(v, "")] -> Just v
                           _         -> Nothing
      _               -> Nothing

peerEscalates :: [TensionEvent] -> Bool
peerEscalates = any (\e -> teKind e == "escalate")

countNonBlankLines :: String -> Int
countNonBlankLines raw =
  length [ln | ln <- lines raw, not (T.null (T.strip (T.pack ln)))]

-- Keep events dated inside the audit window; the window closes on its
-- end date per the tide threshold sheet.
windowFilter :: String -> String -> [TensionEvent] -> [TensionEvent]
windowFilter start end =
  filter (\e -> let d = take 10 (teTs e) in d >= start && d < end)

-- Collapse identical (ts, peer, kind) triples; the first reading wins.
dedupEvents :: [TensionEvent] -> [TensionEvent]
dedupEvents = go []
  where
    go _ [] = []
    go seen (e:rest)
      | key e `elem` seen = go seen rest
      | otherwise = e : go (key e : seen) rest
    key e = (teTs e, tePeer e, teKind e)
