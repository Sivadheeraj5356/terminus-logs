#!/bin/bash
set -euo pipefail

cd /app

mkdir -p /app /tmp/harborlane-ghc /var/lib/harborlane/out

cat > /app/Main.hs <<'HARBORLANE_HASKELL'
{-# LANGUAGE RecordWildCards #-}

module Main where

import Control.Monad (when)
import Data.Bits
import Data.Char (ord)
import Data.List (foldl', intercalate, sort, sortBy)
import qualified Data.Map.Strict as M
import Data.Maybe (fromMaybe)
import qualified Data.Set as S
import Data.Word
import Numeric (showHex)
import System.Directory (createDirectoryIfMissing)
import System.Environment (getArgs)
import System.Exit (die)
import System.FilePath ((</>))
import Text.Printf (printf)

data Segment = Segment
  { segId :: String,
    basin :: String,
    stream :: String,
    cpu :: Int,
    mem :: Int,
    value :: Double,
    replay :: Double,
    work :: Double,
    drift :: Double,
    risk :: Double,
    baseThreshold :: Double,
    noise :: Double,
    overlap :: String,
    affinity :: String,
    lease :: String
  }
  deriving (Show)

data Row = Row
  { enabled :: Bool,
    rowThreshold :: Double,
    priority :: Int,
    rowTier :: String
  }
  deriving (Show)

type SegmentMap = M.Map String Segment

type Policies = [(String, (Int, Int, Int))]

type Plan = M.Map String Row

tiers, streams :: [String]
tiers = ["EDGE", "BULK", "DEFER"]
streams = ["ingest", "ledger", "cache", "repair"]

nActive, cpuLimit, memLimit, tierStreamMin, priorityBandSize, priorityBandBasinMin, priorityBandOverlapMax, affinityMatchMin :: Int
nActive = 44
cpuLimit = 660
memLimit = 1060
tierStreamMin = 2
priorityBandSize = 11
priorityBandBasinMin = 5
priorityBandOverlapMax = 2
affinityMatchMin = 30

tierRanges, streamRanges, bucketRanges :: M.Map String (Int, Int)
tierRanges = M.fromList [("EDGE", (12, 17)), ("BULK", (12, 20)), ("DEFER", (9, 17))]
streamRanges = M.fromList [("ingest", (10, 12)), ("ledger", (10, 12)), ("cache", (10, 12)), ("repair", (10, 12))]
bucketRanges = M.fromList [("track", (16, 24)), ("guard", (12, 20)), ("quarantine", (4, 10))]

main :: IO ()
main = do
  args <- getArgs
  (root, outDir) <- case args of
    ["--root", r, "--out-dir", o] -> pure (r, o)
    _ -> die "usage: harborlane-planner --root ROOT --out-dir OUT_DIR"
  (order, segments, policies, conflicts, held, replayHist) <- loadInput root
  let clear = [sid | sid <- order, S.notMember sid held, maybe False ((== "clear") . lease) (M.lookup sid segments)]
      utility sid =
        let s = segment segments sid
         in replay s * hist replayHist sid * 0.95
              + work s * 0.68
              + drift s * 0.34
              + value s * 0.31
              - 205.0 * (risk s ** 1.35)
      selected0 = initialSelection utility segments policies conflicts clear
      selected1 = improveSelection utility segments policies conflicts held clear selected0
      plan = buildPlan utility order segments selected1
  case hardError segments policies conflicts held plan of
    Just err -> die ("internal hard-rule failure: " ++ err)
    Nothing -> writeOutputs outDir order segments plan

loadInput :: FilePath -> IO ([String], SegmentMap, Policies, S.Set (String, String), S.Set String, M.Map String Double)
loadInput root = do
  segRows <- readTsv (rootPath root "/var/lib/harborlane/data/segments.tsv")
  polRows <- readTsv (rootPath root "/etc/harborlane/policy.tsv")
  confRows <- readTsv (rootPath root "/var/lib/harborlane/data/conflicts.tsv")
  leaseRows <- readTsv (rootPath root "/var/cache/harborlane/state/leases.tsv")
  replayRows <- readTsv (rootPath root "/var/lib/harborlane/data/replay.tsv")
  let order = map (field "segment_id") segRows
      segments = M.fromList [(segId s, s) | s <- map parseSegment segRows]
      policies = [(field "basin" r, (readInt (field "min_enabled" r), readInt (field "max_enabled" r), readInt (field "target_enabled" r))) | r <- polRows]
      conflicts = S.fromList [pair (field "left_segment" r) (field "right_segment" r) | r <- confRows]
      held = S.fromList [field "segment_id" r | r <- leaseRows, field "state" r == "held"]
      replayHist = computeReplayHist order segments replayRows
  pure (order, segments, policies, conflicts, held, replayHist)

parseSegment :: M.Map String String -> Segment
parseSegment row =
  Segment
    { segId = field "segment_id" row,
      basin = field "basin" row,
      stream = field "stream_class" row,
      cpu = readInt (field "cpu" row),
      mem = readInt (field "mem" row),
      value = readDouble (field "value" row),
      replay = readDouble (field "replay" row),
      work = readDouble (field "work" row),
      drift = readDouble (field "drift" row),
      risk = readDouble (field "risk" row),
      baseThreshold = readDouble (field "threshold" row),
      noise = readDouble (field "noise" row),
      overlap = field "overlap" row,
      affinity = field "affinity" row,
      lease = field "lease" row
    }

computeReplayHist :: [String] -> SegmentMap -> [M.Map String String] -> M.Map String Double
computeReplayHist order segments rows =
  let add acc row =
        let sid = field "segment_id" row
            s = segment segments sid
            h = readDouble (field "heat" row)
            q = readDouble (field "pressure" row)
            spicy = readInt (field "spicy" row)
            base = (0.45 + 1.7 * h + 0.8 * q) * if spicy == 1 then 1.15 else 0.72
            edgeM = if affinity s == "EDGE" then 1.09 else 1.0
            riskM = if risk s > 0.7 && spicy == 1 then 1.18 else 1.0
         in M.insertWith (\(a, b) (c, d) -> (a + c, b + d)) sid (base * edgeM * riskM, 1.0) acc
      sums = foldl' add M.empty rows
   in M.fromList [(sid, let (a, b) = M.findWithDefault (0.0, 1.0) sid sums in a / b) | sid <- order]

initialSelection :: (String -> Double) -> SegmentMap -> Policies -> S.Set (String, String) -> [String] -> S.Set String
initialSelection utility segments policies conflicts clear =
  let addForBasin selected (basinName, (_, _, target)) =
        foldl'
          ( \sel sid ->
              if countWhere (\x -> basin (segment segments x) == basinName) (S.toList sel) >= target
                then sel
                else
                  let proposal = S.insert sid sel
                   in if S.notMember sid sel && not (conflictsWith conflicts sel sid) && withinBudget segments proposal then proposal else sel
          )
          selected
          (sortByKey (\sid -> (- utility sid, sid)) [sid | sid <- clear, basin (segment segments sid) == basinName])
      selectedTargets = foldl' addForBasin S.empty policies
      fill selected sid =
        if S.size selected >= nActive || S.member sid selected || conflictsWith conflicts selected sid
          then selected
          else
            let proposal = S.insert sid selected
                b = basin (segment segments sid)
                basinCount = countWhere (\x -> basin (segment segments x) == b) (S.toList proposal)
                hi = maybe 99 (\(_, h, _) -> h) (lookup b policies)
             in if basinCount <= hi && withinBudget segments proposal then proposal else selected
   in foldl' fill selectedTargets (sortByKey (\sid -> (- utility sid, sid)) clear)

improveSelection :: (String -> Double) -> SegmentMap -> Policies -> S.Set (String, String) -> S.Set String -> [String] -> S.Set String -> S.Set String
improveSelection utility segments policies conflicts held clear start = phases 0 start
  where
    phases 4 selected = selected
    phases n selected = phases (n + 1) (passes 0 selected)
    passes 100 selected =
      if S.size selected == nActive then selected else repair selected
    passes n selected =
      case bestSwap selected of
        Nothing -> repair selected
        Just next -> passes (n + 1) next
    repair selected =
      foldl'
        ( \sel sid ->
            if S.size sel >= nActive || S.member sid sel || conflictsWith conflicts sel sid
              then sel
              else
                let proposal = S.insert sid sel
                 in if selectionPenalty segments policies conflicts held proposal <= selectionPenalty segments policies conflicts held sel && withinBudget segments proposal then proposal else sel
        )
        selected
        (sortByKey (\sid -> (- utility sid, sid)) clear)
    score selected = sum [utility sid | sid <- S.toList selected] - selectionPenalty segments policies conflicts held selected * 120.0
    bestSwap selected =
      let current = score selected
          outs = sortByKey (\sid -> (utility sid, sid)) (S.toList selected)
          inns = take 120 (sortByKey (\sid -> (- utility sid, sid)) [sid | sid <- clear, S.notMember sid selected])
          candidates =
            [ (score proposal, proposal)
              | outSid <- outs,
                let base = S.delete outSid selected,
                inSid <- inns,
                not (conflictsWith conflicts base inSid),
                let proposal = S.insert inSid base,
                score proposal > current + 1.0e-9
            ]
       in snd <$> maybeMaximum candidates

selectionPenalty :: SegmentMap -> Policies -> S.Set (String, String) -> S.Set String -> S.Set String -> Double
selectionPenalty segments policies conflicts held selected =
  let xs = S.toList selected
      over amount weight = fromIntegral (max 0 amount) * weight
      cpuTotal = sum [cpu (segment segments sid) | sid <- xs]
      memTotal = sum [mem (segment segments sid) | sid <- xs]
      heldPenalty = if any (\sid -> S.member sid held || lease (segment segments sid) == "held") xs then 10000.0 else 0.0
      conflictPenalty = sum [3000.0 | (a, b) <- S.toList conflicts, S.member a selected, S.member b selected]
      basinCounts = countMap [basin (segment segments sid) | sid <- xs]
      basinPenalty =
        sum
          [ over (lo - count basinName basinCounts) 800.0
              + over (count basinName basinCounts - hi) 800.0
              + fromIntegral (abs (count basinName basinCounts - target)) * 5.0
            | (basinName, (lo, hi, target)) <- policies
          ]
      streamCounts = countMap [stream (segment segments sid) | sid <- xs]
      streamPenalty =
        sum
          [ over (lo - count name streamCounts) 900.0
              + over (count name streamCounts - hi) 900.0
              + fromIntegral (abs (count name streamCounts - 11)) * 12.0
            | (name, (lo, hi)) <- M.toList streamRanges
          ]
      overlapPenalty = sum [over (n - 3) 500.0 | n <- M.elems (countMap [overlap (segment segments sid) | sid <- xs])]
   in abs (S.size selected - nActive) `intMul` 1000.0
        + over (cpuTotal - cpuLimit) 20.0
        + over (memTotal - memLimit) 10.0
        + heldPenalty
        + conflictPenalty
        + basinPenalty
        + streamPenalty
        + overlapPenalty

buildPlan :: (String -> Double) -> [String] -> SegmentMap -> S.Set String -> Plan
buildPlan utility order segments selected =
  let tiersAssigned = assignTiers utility segments selected
      thresholds = assignThresholds utility segments tiersAssigned selected
      ranked = buildPriority utility segments tiersAssigned thresholds selected
      off = M.fromList [(sid, Row False 0.0 0 "OFF") | sid <- order]
   in foldl' (\m (p, sid) -> M.insert sid (Row True (thresholds M.! sid) p (tiersAssigned M.! sid)) m) off (zip [1 ..] ranked)

assignTiers :: (String -> Double) -> SegmentMap -> S.Set String -> M.Map String String
assignTiers utility segments selected = balanceCells (balanceRanges 0 assignedAll)
  where
    selectedList = S.toList selected
    targetCounts = M.fromList [("EDGE", 15), ("BULK", 15), ("DEFER", 14)]
    highRisk = M.fromList [(sid, "DEFER") | sid <- selectedList, risk (segment segments sid) >= 0.86]
    seeded = foldl' seedCell highRisk [(st, tr) | st <- streams, tr <- tiers]
    assignedAll = foldl' assignOne seeded (sortByKey (\sid -> (- maximum [tierValue utility segments sid tr | tr <- tiers], sid)) [sid | sid <- selectedList, M.notMember sid seeded])
    allowed sid tr = risk (segment segments sid) < 0.86 || tr == "DEFER"
    assignOne acc sid =
      let counts = countMap (M.elems acc)
          available = [tr | tr <- tiers, count tr counts < count tr targetCounts, allowed sid tr]
          fallback = [tr | tr <- tiers, let (_, hi) = tierRanges M.! tr, count tr counts < hi, allowed sid tr]
          choices = if null available then fallback else available
       in M.insert sid (bestBy (\tr -> (tierValue utility segments sid tr, tr)) choices) acc
    seedCell acc (st, tr) =
      let streamSids = [sid | sid <- selectedList, stream (segment segments sid) == st]
       in fillCell acc streamSids tr
    fillCell acc streamSids tr =
      let cellCounts = countMap [(tier, stream (segment segments sid)) | (sid, tier) <- M.toList acc]
       in if count (tr, streamName streamSids) cellCounts >= tierStreamMin
            then acc
            else
              let c1 = [sid | sid <- streamSids, M.notMember sid acc, allowed sid tr]
                  c2 = [sid | sid <- streamSids, M.lookup sid acc /= Just tr, allowed sid tr]
                  candidates = if null c1 then c2 else c1
               in if null candidates then acc else fillCell (M.insert (bestBy (\x -> (tierValue utility segments x tr, utility x, x)) candidates) tr acc) streamSids tr
    streamName [] = ""
    streamName (sid : _) = stream (segment segments sid)
    balanceRanges 40 acc =
      acc
    balanceRanges n acc =
      let (changed, next) = foldl' adjustTier (False, acc) tiers
       in if changed then balanceRanges (n + 1) next else next
    adjustTier (changed, acc) tr =
      let counts = countMap (M.elems acc)
          (lo, hi) = tierRanges M.! tr
       in if count tr counts < lo
            then
              let candidates =
                    [ sid
                      | sid <- selectedList,
                        M.lookup sid acc /= Just tr,
                        allowed sid tr,
                        let old = acc M.! sid,
                        count old counts > fst (tierRanges M.! old)
                    ]
               in if null candidates
                    then (changed, acc)
                    else (True, M.insert (bestBy (\x -> (tierValue utility segments x tr - tierValue utility segments x (acc M.! x), x)) candidates) tr acc)
            else
              if count tr counts > hi
                then
                  let candidates = [sid | sid <- selectedList, M.lookup sid acc == Just tr]
                      sid = bestBy (\x -> (- tierValue utility segments x tr, x)) candidates
                      dests = [d | d <- tiers, d /= tr, let (_, dhi) = tierRanges M.! d, count d counts < dhi, allowed sid d]
                   in if null candidates || null dests then (changed, acc) else (True, M.insert sid (bestBy (\d -> (tierValue utility segments sid d, d)) dests) acc)
                else (changed, acc)
    balanceCells acc = cellLoop 0 acc
    cellLoop 40 acc =
      acc
    cellLoop n acc =
      let (changed, next) = foldl' adjustCell (False, acc) [(tr, st) | tr <- tiers, st <- streams]
       in if changed then cellLoop (n + 1) next else next
    adjustCell (changed, acc) (tr, st) =
      let cells = countMap [(tier, stream (segment segments sid)) | (sid, tier) <- M.toList acc]
       in if count (tr, st) cells >= tierStreamMin
            then (changed, acc)
            else
              let tierCounts = countMap (M.elems acc)
                  candidates =
                    [ sid
                      | sid <- selectedList,
                        stream (segment segments sid) == st,
                        M.lookup sid acc /= Just tr,
                        allowed sid tr,
                        let old = acc M.! sid,
                        count old tierCounts > fst (tierRanges M.! old),
                        count (old, st) cells > tierStreamMin
                    ]
               in if null candidates then (changed, acc) else (True, M.insert (bestBy (\x -> (tierValue utility segments x tr - tierValue utility segments x (acc M.! x), x)) candidates) tr acc)

tierValue :: (String -> Double) -> SegmentMap -> String -> String -> Double
tierValue _ segments sid tr =
  let s = segment segments sid
      trep = tierFactor tr [("EDGE", 1.13), ("BULK", 0.98), ("DEFER", 0.77)]
      twrk = tierFactor tr [("EDGE", 0.93), ("BULK", 1.07), ("DEFER", 0.84)]
      trsk = tierFactor tr [("EDGE", 1.24), ("BULK", 0.94), ("DEFER", 0.60)]
      high = if risk s >= 0.86 then if tr == "DEFER" then 500.0 else -10000.0 else 0.0
   in replay s * trep * 0.62
        + (work s * 0.72 + value s * 0.34) * twrk * 0.43
        - (risk s ** 1.35) * (0.70 + value s / 240.0) * trsk * 135.0
        + (if tr == affinity s then 70.0 else 0.0)
        + high

assignThresholds :: (String -> Double) -> SegmentMap -> M.Map String String -> S.Set String -> M.Map String Double
assignThresholds utility segments tiersAssigned selected =
  let selectedList = S.toList selected
      high = [sid | sid <- selectedList, risk (segment segments sid) >= 0.86]
      initial = M.fromList [(sid, "quarantine") | sid <- high]
      remaining0 = [sid | sid <- selectedList, M.notMember sid initial]
      qNeed = max 0 (8 - M.size initial)
      qRank = sortByKey (\sid -> (-(baseThreshold (segment segments sid) + risk (segment segments sid) * 0.8), utility sid, sid)) remaining0
      afterQ = foldl' (\m sid -> M.insert sid "quarantine" m) initial (take qNeed qRank)
      remaining1 = [sid | sid <- remaining0, M.notMember sid afterQ]
      trackRank = sortByKey (\sid -> (-(replay (segment segments sid) * tierFactor (tiersAssigned M.! sid) [("EDGE", 1.15), ("BULK", 1.0), ("DEFER", 0.75)] - 65.0 * risk (segment segments sid)), sid)) remaining1
      afterTrack = foldl' (\m sid -> M.insert sid "track" m) afterQ (take 20 trackRank)
      buckets = foldl' (\m sid -> M.insertWith (\_ old -> old) sid "guard" m) afterTrack remaining1
   in M.mapWithKey thresholdFor buckets
  where
    thresholdFor sid bucketName =
      let s = segment segments sid
          optimum = 1.54 + baseThreshold s * 0.28
          raw =
            case bucketName of
              "track" -> if (tiersAssigned M.! sid) == "EDGE" then 1.52 else 1.54
              "guard" -> min 1.64 (max 1.55 optimum)
              _ -> max 1.66 (min 1.78 optimum)
          high = if risk s >= 0.86 then max raw 1.66 else raw
       in rounded2 high

buildPriority :: (String -> Double) -> SegmentMap -> M.Map String String -> M.Map String Double -> S.Set String -> [String]
buildPriority utility segments tiersAssigned thresholds selected = go 1 selected [] M.empty M.empty M.empty M.empty M.empty S.empty M.empty M.empty M.empty S.empty M.empty
  where
    selectedList = S.toList selected
    totalTier = countMap [tiersAssigned M.! sid | sid <- selectedList]
    totalStream = countMap [stream (segment segments sid) | sid <- selectedList]
    go rank remaining ranked groupCount usedTier usedStream leadingTier leadingStream leadingBasin leadingGroup bandTier bandStream bandBasin bandOverlap
      | rank > nActive = reverse ranked
      | otherwise =
          let freshBand = (rank - 1) `mod` priorityBandSize == 0
              bandTier0 = if freshBand then M.empty else bandTier
              bandStream0 = if freshBand then M.empty else bandStream
              bandBasin0 = if freshBand then S.empty else bandBasin
              bandOverlap0 = if freshBand then M.empty else bandOverlap
              candidates = S.toList remaining
              feasible = filter (bandFeasible rank usedTier usedStream bandTier0 bandStream0 bandBasin0 bandOverlap0) candidates
              choices = if null feasible then candidates else feasible
              sid = bestBy (priorityKey rank groupCount leadingTier leadingStream leadingBasin leadingGroup bandTier0 bandStream0 bandBasin0 bandOverlap0) choices
              s = segment segments sid
              group = overlap s
              tr = tiersAssigned M.! sid
              st = stream s
              remaining' = S.delete sid remaining
              groupCount' = M.insertWith (+) group 1 groupCount
              usedTier' = M.insertWith (+) tr 1 usedTier
              usedStream' = M.insertWith (+) st 1 usedStream
              leadingTier' = if rank <= 18 then M.insertWith (+) tr 1 leadingTier else leadingTier
              leadingStream' = if rank <= 18 then M.insertWith (+) st 1 leadingStream else leadingStream
              leadingBasin' = if rank <= 18 then S.insert (basin s) leadingBasin else leadingBasin
              leadingGroup' = if rank <= 18 then M.insertWith (+) group 1 leadingGroup else leadingGroup
              bandTier' = M.insertWith (+) tr 1 bandTier0
              bandStream' = M.insertWith (+) st 1 bandStream0
              bandBasin' = S.insert (basin s) bandBasin0
              bandOverlap' = M.insertWith (+) group 1 bandOverlap0
           in go (rank + 1) remaining' (sid : ranked) groupCount' usedTier' usedStream' leadingTier' leadingStream' leadingBasin' leadingGroup' bandTier' bandStream' bandBasin' bandOverlap'
    priorityKey rank groupCount leadingTier leadingStream leadingBasin leadingGroup bandTier bandStream bandBasin bandOverlap sid =
      let s = segment segments sid
          tr = tiersAssigned M.! sid
          threshold = thresholds M.! sid
          det = max 0.30 (1.17 - 0.295 * threshold - 0.07 * risk s + if tr == "EDGE" then 0.035 else 0.0 - if tr == "DEFER" then 0.025 else 0.0)
          fade = fadeAt (count (overlap s) groupCount)
          base =
            replay s * det * tierFactor tr [("EDGE", 1.13), ("BULK", 0.98), ("DEFER", 0.77)] * fade
              + (work s * 0.72 + value s * 0.34) * tierFactor tr [("EDGE", 0.93), ("BULK", 1.07), ("DEFER", 0.84)] * fade
              - risk s * 55.0
          leadingBonus
            | rank > 18 = if count (overlap s) groupCount == 0 then 100.0 else 0.0
            | otherwise =
                (if count (overlap s) leadingGroup >= 2 then -100000.0 else 0.0)
                  + (if count tr leadingTier >= tierLeadingMax tr then -100000.0 else 0.0)
                  + (if count tr leadingTier < tierLeadingMin tr then 20000.0 else 0.0)
                  + (if count (stream s) leadingStream == 0 then 15000.0 else 0.0)
                  + (if S.notMember (basin s) leadingBasin && S.size leadingBasin < 7 then 9000.0 else 0.0)
                  + (if count (overlap s) groupCount == 0 then 250.0 else 0.0)
          bandBonus =
            (if count tr bandTier < bandTierMin tr then 42000.0 else 0.0)
              + (if count (stream s) bandStream < bandStreamMin then 36000.0 else 0.0)
              + (if S.notMember (basin s) bandBasin && S.size bandBasin < priorityBandBasinMin then 12000.0 else 0.0)
              + (if count (overlap s) bandOverlap == 0 then 900.0 else -350.0 * fromIntegral (count (overlap s) bandOverlap))
       in (base + leadingBonus + bandBonus, sid)
    bandFeasible rank usedTier usedStream bandTier bandStream bandBasin bandOverlap sid =
      let s = segment segments sid
          tr = tiersAssigned M.! sid
          st = stream s
          group = overlap s
          slotsLeft = priorityBandSize - ((rank - 1) `mod` priorityBandSize) - 1
          futureBands = (nActive - rank - slotsLeft) `div` priorityBandSize
          usedTierAfter = M.insertWith (+) tr 1 usedTier
          usedStreamAfter = M.insertWith (+) st 1 usedStream
          tierAfter = M.insertWith (+) tr 1 bandTier
          streamAfter = M.insertWith (+) st 1 bandStream
          basinAfter = S.insert (basin s) bandBasin
          overlapAfter = M.insertWith (+) group 1 bandOverlap
          tierDeficit t = max 0 (bandTierMin t - count t tierAfter)
          streamDeficit x = max 0 (bandStreamMin - count x streamAfter)
          tierDeficitSum = sum [tierDeficit t | t <- tiers]
          streamDeficitSum = sum [streamDeficit x | x <- streams]
          tierFutureOk t =
            let left = count t totalTier - count t usedTierAfter
             in left >= tierDeficit t + futureBands * bandTierMin t
                  && left <= slotsLeft + futureBands * bandTierMax t
          streamFutureOk x =
            let left = count x totalStream - count x usedStreamAfter
             in left >= streamDeficit x + futureBands * bandStreamMin
                  && left <= slotsLeft + futureBands * bandStreamMax
       in count tr tierAfter <= bandTierMax tr
            && count st streamAfter <= bandStreamMax
            && count group overlapAfter <= priorityBandOverlapMax
            && tierDeficitSum <= slotsLeft
            && streamDeficitSum <= slotsLeft
            && all tierFutureOk tiers
            && all streamFutureOk streams
            && S.size basinAfter + slotsLeft >= priorityBandBasinMin

hardError :: SegmentMap -> Policies -> S.Set (String, String) -> S.Set String -> Plan -> Maybe String
hardError segments policies conflicts held plan =
  let active = activeByPriority plan
      activeSet = S.fromList active
      priorities = sort [priority (plan M.! sid) | sid <- active]
      byBasin = countMap [basin (segment segments sid) | sid <- active]
      byTier = countMap [rowTier (plan M.! sid) | sid <- active]
      byStream = countMap [stream (segment segments sid) | sid <- active]
      byCell = countMap [(rowTier (plan M.! sid), stream (segment segments sid)) | sid <- active]
      byBucket = countMap [thresholdBucket (rowThreshold (plan M.! sid)) | sid <- active]
      byOverlap = countMap [overlap (segment segments sid) | sid <- active]
      leading = take 18 active
      leadingTier = countMap [rowTier (plan M.! sid) | sid <- leading]
      leadingOverlap = countMap [overlap (segment segments sid) | sid <- leading]
      failIf cond msg = if cond then Just msg else Nothing
      bandError (bandNo, band) =
        let bandTier = countMap [rowTier (plan M.! sid) | sid <- band]
            bandStream = countMap [stream (segment segments sid) | sid <- band]
            bandOverlap = countMap [overlap (segment segments sid) | sid <- band]
         in firstJust
              [ firstJust [failIf (count tr bandTier < bandTierMin tr || count tr bandTier > bandTierMax tr) ("priority-band-tier:" ++ show bandNo ++ ":" ++ tr) | tr <- tiers],
                firstJust [failIf (count st bandStream < bandStreamMin || count st bandStream > bandStreamMax) ("priority-band-stream:" ++ show bandNo ++ ":" ++ st) | st <- streams],
                failIf (S.size (S.fromList [basin (segment segments sid) | sid <- band]) < priorityBandBasinMin) ("priority-band-basin-diversity:" ++ show bandNo),
                failIf (any (> priorityBandOverlapMax) (M.elems bandOverlap)) ("priority-band-overlap:" ++ show bandNo)
              ]
   in firstJust
        [ failIf (length active /= nActive) "wrong-active-count",
          failIf (priorities /= [1 .. nActive]) "priorities-not-contiguous",
          failIf (sum [cpu (segment segments sid) | sid <- active] > cpuLimit) "cpu-limit",
          failIf (sum [mem (segment segments sid) | sid <- active] > memLimit) "mem-limit",
          failIf (any (\sid -> S.member sid held || lease (segment segments sid) == "held") active) "held-lease-enabled",
          failIf (any (\(a, b) -> S.member a activeSet && S.member b activeSet) (S.toList conflicts)) "conflict-pair-enabled",
          firstJust [failIf (count b byBasin < lo || count b byBasin > hi) ("basin-window:" ++ b) | (b, (lo, hi, _)) <- policies],
          firstJust [failIf (count tr byTier < lo || count tr byTier > hi) ("tier-window:" ++ tr) | (tr, (lo, hi)) <- M.toList tierRanges],
          firstJust [failIf (count st byStream < lo || count st byStream > hi) ("stream-window:" ++ st) | (st, (lo, hi)) <- M.toList streamRanges],
          firstJust [failIf (count (tr, st) byCell < tierStreamMin) ("tier-stream-window:" ++ tr ++ ":" ++ st) | tr <- tiers, st <- streams],
          firstJust [failIf (count b byBucket < lo || count b byBucket > hi) ("threshold-bucket:" ++ b) | (b, (lo, hi)) <- M.toList bucketRanges],
          failIf (any (> 3) (M.elems byOverlap)) "overlap-group-overfilled",
          failIf (length (S.fromList [basin (segment segments sid) | sid <- leading]) < 7) "leading-band-basin-diversity",
          failIf (length (S.fromList [stream (segment segments sid) | sid <- leading]) < 4) "leading-band-stream-diversity",
          failIf (any (> 2) (M.elems leadingOverlap)) "leading-band-overlap-cluster",
          failIf (count "EDGE" leadingTier < 4 || count "EDGE" leadingTier > 8 || count "BULK" leadingTier < 4 || count "BULK" leadingTier > 8 || count "DEFER" leadingTier < 3 || count "DEFER" leadingTier > 7) "leading-band-tier-mix",
          firstJust [failIf (risk (segment segments sid) >= 0.86 && (rowTier (plan M.! sid) /= "DEFER" || rowThreshold (plan M.! sid) < 1.66)) ("high-risk-not-quarantined:" ++ sid) | sid <- active],
          failIf (countWhere (\sid -> rowTier (plan M.! sid) == affinity (segment segments sid)) active < affinityMatchMin) "affinity-match-floor",
          firstJust (map bandError (zip [(1 :: Int) ..] (chunksOf priorityBandSize active)))
        ]

writeOutputs :: FilePath -> [String] -> SegmentMap -> Plan -> IO ()
writeOutputs outDir order segments plan = do
  createDirectoryIfMissing True outDir
  let planPath = outDir </> "plan.tsv"
      hsPath = outDir </> "Plan.hs"
      active = [sid | sid <- order, enabled (plan M.! sid)]
      tCounts = countMap [rowTier (plan M.! sid) | sid <- active]
      cCounts = countMap [(rowTier (plan M.! sid), stream (segment segments sid)) | sid <- active]
      bCounts = countMap [thresholdBucket (rowThreshold (plan M.! sid)) | sid <- active]
      aCounts = countMap [rowTier (plan M.! sid) | sid <- active, rowTier (plan M.! sid) == affinity (segment segments sid)]
      pBands = priorityBandSummaries segments plan
      tsv = renderTsv order plan
      digest = sha256Hex tsv
  writeFile planPath tsv
  writeFile hsPath (renderPlanHs order plan digest tCounts cCounts bCounts aCounts pBands)

renderTsv :: [String] -> Plan -> String
renderTsv order plan =
  unlines $
    intercalate "\t" ["segment_id", "enabled", "threshold_param", "priority", "routing_tier"] :
    [ intercalate "\t" [sid, if enabled row then "1" else "0", printf "%.2f" (rowThreshold row), show (priority row), rowTier row]
      | sid <- order,
        let row = plan M.! sid
    ]

renderPlanHs :: [String] -> Plan -> String -> M.Map String Int -> M.Map (String, String) Int -> M.Map String Int -> M.Map String Int -> [(Int, Int, Int, Int, Int, Int, Int, Int)] -> String
renderPlanHs order plan digest tCounts cCounts bCounts aCounts pBands =
  unlines $
    [ "module Plan where",
      "",
      "planRows :: [(String, Int, Double, Int, String)]",
      "planRows ="
    ]
      ++ renderList [printf "(%s, %d, %.2f, %d, %s)" (show sid) (if enabled row then (1 :: Int) else 0) (rowThreshold row) (priority row) (show (rowTier row)) | sid <- order, let row = plan M.! sid]
      ++ [ "",
           "planDigest :: String",
           "planDigest = " ++ show digest,
           "",
           "tierCounts :: [(String, Int)]",
           "tierCounts ="
         ]
      ++ renderList [printf "(%s, %d)" (show tr) (count tr tCounts) | tr <- tiers]
      ++ [ "",
           "streamTierCounts :: [((String, String), Int)]",
           "streamTierCounts ="
         ]
      ++ renderList [printf "((%s, %s), %d)" (show tr) (show st) (count (tr, st) cCounts) | tr <- tiers, st <- streams]
      ++ [ "",
           "thresholdBuckets :: [(String, Int)]",
           "thresholdBuckets ="
         ]
      ++ renderList [printf "(%s, %d)" (show b) (count b bCounts) | b <- ["track", "guard", "quarantine"]]
      ++ [ "",
           "affinityCounts :: [(String, Int)]",
           "affinityCounts ="
         ]
      ++ renderList [printf "(%s, %d)" (show tr) (count tr aCounts) | tr <- tiers]
      ++ [ "",
           "priorityBands :: [(Int, Int, Int, Int, Int, Int, Int, Int)]",
           "priorityBands ="
         ]
      ++ renderList [printf "(%d, %d, %d, %d, %d, %d, %d, %d)" band edge bulk defer ingest ledger cache repair | (band, edge, bulk, defer, ingest, ledger, cache, repair) <- pBands]
  where
    renderList [] = ["  []"]
    renderList (x : xs) = ("  [ " ++ x) : ["  , " ++ y | y <- xs] ++ ["  ]"]

priorityBandSummaries :: SegmentMap -> Plan -> [(Int, Int, Int, Int, Int, Int, Int, Int)]
priorityBandSummaries segments plan =
  [ (bandNo, count "EDGE" tierCounts, count "BULK" tierCounts, count "DEFER" tierCounts, count "ingest" streamCounts, count "ledger" streamCounts, count "cache" streamCounts, count "repair" streamCounts)
    | (bandNo, band) <- zip [(1 :: Int) ..] (chunksOf priorityBandSize (activeByPriority plan)),
      let tierCounts = countMap [rowTier (plan M.! sid) | sid <- band],
      let streamCounts = countMap [stream (segment segments sid) | sid <- band]
  ]

activeByPriority :: Plan -> [String]
activeByPriority plan = sortByKey (\sid -> (priority (plan M.! sid), sid)) [sid | (sid, row) <- M.toList plan, enabled row]

rootPath :: FilePath -> FilePath -> FilePath
rootPath root rel = root </> dropWhile (== '/') rel

readTsv :: FilePath -> IO [M.Map String String]
readTsv path = do
  content <- readFile path
  case lines content of
    [] -> pure []
    headerLine : rowLines -> do
      let headers = splitTab headerLine
      pure [M.fromList (zip headers (splitTab line)) | line <- rowLines, not (null line)]

splitTab :: String -> [String]
splitTab [] = [""]
splitTab input =
  case break (== '\t') input of
    (chunk, []) -> [chunk]
    (chunk, _ : rest) -> chunk : splitTab rest

field :: String -> M.Map String String -> String
field name row = fromMaybe (error ("missing field " ++ name)) (M.lookup name row)

segment :: SegmentMap -> String -> Segment
segment segments sid = fromMaybe (error ("unknown segment " ++ sid)) (M.lookup sid segments)

readInt :: String -> Int
readInt = read

readDouble :: String -> Double
readDouble = read

hist :: M.Map String Double -> String -> Double
hist m sid = M.findWithDefault 1.0 sid m

pair :: String -> String -> (String, String)
pair a b = if a <= b then (a, b) else (b, a)

conflictsWith :: S.Set (String, String) -> S.Set String -> String -> Bool
conflictsWith conflicts selected sid = any (\x -> S.member (pair sid x) conflicts) (S.toList selected)

withinBudget :: SegmentMap -> S.Set String -> Bool
withinBudget segments selected =
  sum [cpu (segment segments sid) | sid <- S.toList selected] <= cpuLimit
    && sum [mem (segment segments sid) | sid <- S.toList selected] <= memLimit

countMap :: (Ord a) => [a] -> M.Map a Int
countMap = M.fromListWith (+) . map (\x -> (x, 1))

count :: (Ord a) => a -> M.Map a Int -> Int
count key = M.findWithDefault 0 key

countWhere :: (a -> Bool) -> [a] -> Int
countWhere f = length . filter f

intMul :: Int -> Double -> Double
intMul n x = fromIntegral n * x

tierFactor :: String -> [(String, Double)] -> Double
tierFactor tr values = fromMaybe 1.0 (lookup tr values)

thresholdBucket :: Double -> String
thresholdBucket x
  | x <= 1.54 = "track"
  | x <= 1.64 = "guard"
  | otherwise = "quarantine"

tierLeadingMin, tierLeadingMax, bandTierMin, bandTierMax :: String -> Int
tierLeadingMin "EDGE" = 4
tierLeadingMin "BULK" = 4
tierLeadingMin _ = 3
tierLeadingMax "EDGE" = 8
tierLeadingMax "BULK" = 8
tierLeadingMax _ = 7
bandTierMin _ = 2
bandTierMax _ = 5

bandStreamMin, bandStreamMax :: Int
bandStreamMin = 2
bandStreamMax = 4

fadeAt :: Int -> Double
fadeAt n = [1.0, 0.64, 0.39, 0.23, 0.13, 0.08] !! min n 5

rounded2 :: Double -> Double
rounded2 x = fromIntegral (round (x * 100.0) :: Int) / 100.0

sortByKey :: (Ord b) => (a -> b) -> [a] -> [a]
sortByKey f = sortBy (\a b -> compare (f a) (f b))

bestBy :: (Ord b) => (a -> b) -> [a] -> a
bestBy f xs =
  case xs of
    [] -> error "bestBy on empty list"
    x : rest -> foldl' (\best item -> if f item > f best then item else best) x rest

maybeMaximum :: (Ord a) => [a] -> Maybe a
maybeMaximum [] = Nothing
maybeMaximum xs = Just (maximum xs)

firstJust :: [Maybe a] -> Maybe a
firstJust = foldr (\x acc -> case x of Just _ -> x; Nothing -> acc) Nothing

hexValue :: String -> Int
hexValue = foldl' (\acc c -> acc * 16 + digit c) 0
  where
    digit c
      | c >= '0' && c <= '9' = ord c - ord '0'
      | c >= 'a' && c <= 'f' = 10 + ord c - ord 'a'
      | c >= 'A' && c <= 'F' = 10 + ord c - ord 'A'
      | otherwise = 0

sha256Hex :: String -> String
sha256Hex input =
  concatMap wordHex $
    foldl' processChunk initialHash (chunksOf 64 padded)
  where
    bytes = map (fromIntegral . ord) input :: [Word8]
    bitLen = fromIntegral (length bytes) * 8 :: Word64
    withOne = bytes ++ [0x80]
    padLen = (56 - length withOne `mod` 64) `mod` 64
    padded = withOne ++ replicate padLen 0 ++ word64Bytes bitLen

initialHash :: [Word32]
initialHash = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]

shaK :: [Word32]
shaK =
  [ 0x428a2f98,
    0x71374491,
    0xb5c0fbcf,
    0xe9b5dba5,
    0x3956c25b,
    0x59f111f1,
    0x923f82a4,
    0xab1c5ed5,
    0xd807aa98,
    0x12835b01,
    0x243185be,
    0x550c7dc3,
    0x72be5d74,
    0x80deb1fe,
    0x9bdc06a7,
    0xc19bf174,
    0xe49b69c1,
    0xefbe4786,
    0x0fc19dc6,
    0x240ca1cc,
    0x2de92c6f,
    0x4a7484aa,
    0x5cb0a9dc,
    0x76f988da,
    0x983e5152,
    0xa831c66d,
    0xb00327c8,
    0xbf597fc7,
    0xc6e00bf3,
    0xd5a79147,
    0x06ca6351,
    0x14292967,
    0x27b70a85,
    0x2e1b2138,
    0x4d2c6dfc,
    0x53380d13,
    0x650a7354,
    0x766a0abb,
    0x81c2c92e,
    0x92722c85,
    0xa2bfe8a1,
    0xa81a664b,
    0xc24b8b70,
    0xc76c51a3,
    0xd192e819,
    0xd6990624,
    0xf40e3585,
    0x106aa070,
    0x19a4c116,
    0x1e376c08,
    0x2748774c,
    0x34b0bcb5,
    0x391c0cb3,
    0x4ed8aa4a,
    0x5b9cca4f,
    0x682e6ff3,
    0x748f82ee,
    0x78a5636f,
    0x84c87814,
    0x8cc70208,
    0x90befffa,
    0xa4506ceb,
    0xbef9a3f7,
    0xc67178f2
  ]

processChunk :: [Word32] -> [Word8] -> [Word32]
processChunk [h0, h1, h2, h3, h4, h5, h6, h7] chunk =
  let w0 = map word32FromBytes (chunksOf 4 chunk)
      w = extendWords w0
      (a, b, c, d, e, f, g, h) = foldl' roundStep (h0, h1, h2, h3, h4, h5, h6, h7) (zip shaK w)
   in zipWith (+) [h0, h1, h2, h3, h4, h5, h6, h7] [a, b, c, d, e, f, g, h]
processChunk _ _ = error "bad sha256 chunk"

roundStep :: (Word32, Word32, Word32, Word32, Word32, Word32, Word32, Word32) -> (Word32, Word32) -> (Word32, Word32, Word32, Word32, Word32, Word32, Word32, Word32)
roundStep (a, b, c, d, e, f, g, h) (k, w) =
  let s1 = rotateR e 6 `xor` rotateR e 11 `xor` rotateR e 25
      ch = (e .&. f) `xor` (complement e .&. g)
      temp1 = h + s1 + ch + k + w
      s0 = rotateR a 2 `xor` rotateR a 13 `xor` rotateR a 22
      maj = (a .&. b) `xor` (a .&. c) `xor` (b .&. c)
      temp2 = s0 + maj
   in (temp1 + temp2, a, b, c, d + temp1, e, f, g)

extendWords :: [Word32] -> [Word32]
extendWords w0 = take 64 (go w0)
  where
    go ws
      | length ws >= 64 = ws
      | otherwise =
          let i = length ws
              s0 = rotateR (ws !! (i - 15)) 7 `xor` rotateR (ws !! (i - 15)) 18 `xor` shiftR (ws !! (i - 15)) 3
              s1 = rotateR (ws !! (i - 2)) 17 `xor` rotateR (ws !! (i - 2)) 19 `xor` shiftR (ws !! (i - 2)) 10
              next = ws !! (i - 16) + s0 + ws !! (i - 7) + s1
           in go (ws ++ [next])

word32FromBytes :: [Word8] -> Word32
word32FromBytes [a, b, c, d] =
  shiftL (fromIntegral a) 24
    .|. shiftL (fromIntegral b) 16
    .|. shiftL (fromIntegral c) 8
    .|. fromIntegral d
word32FromBytes _ = 0

word64Bytes :: Word64 -> [Word8]
word64Bytes w = [fromIntegral (shiftR w s .&. 0xff) | s <- ([56, 48 .. 0] :: [Int])]

chunksOf :: Int -> [a] -> [[a]]
chunksOf _ [] = []
chunksOf n xs = let (a, b) = splitAt n xs in a : chunksOf n b

wordHex :: Word32 -> String
wordHex w =
  let h = showHex w ""
   in replicate (8 - length h) '0' ++ h
HARBORLANE_HASKELL

ghc -O2 -v0 -outputdir /tmp/harborlane-ghc -o /tmp/harborlane-planner /app/Main.hs
/tmp/harborlane-planner --root / --out-dir /var/lib/harborlane/out
/opt/verifier-venv/bin/python /opt/harborlane/scripts/model.py --json --plan /var/lib/harborlane/out/plan.tsv >/tmp/harborlane-oracle-score.json

grep -q '"passes_gate": true' /tmp/harborlane-oracle-score.json
