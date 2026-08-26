{-# LANGUAGE OverloadedStrings #-}

module Main (main) where

import           Control.Monad         (forM)
import           Data.Aeson            (Value (..), eitherDecodeStrict)
import qualified Data.Aeson.Key        as Key
import qualified Data.Aeson.KeyMap     as KM
import qualified Data.ByteString       as BS
import qualified Data.ByteString.Char8 as BS8
import qualified Data.Map.Strict       as Map
import           Data.List             (foldl', isPrefixOf, sortBy, sortOn)
import           Data.Maybe            (fromMaybe, mapMaybe)
import           Data.Ord              (comparing)
import qualified Data.Text             as T
import           Keelmark.Classify     (classifyBlock, dominantPeer, effTenths, loadIndex, padTensionTs, selectLastEvent)
import           Keelmark.Emit         (writeReports)
import           Keelmark.Scan         (countNonBlankLines, dedupEvents, parseTensionEvents, peerEscalates, windowFilter)
import           Keelmark.Types
import           System.Directory      (createDirectoryIfMissing, doesFileExist)
import           System.Environment    (lookupEnv)
import           System.FilePath       ((</>))

main :: IO ()
main = do
  root <- fromMaybe "/app" <$> lookupEnv "HARBOR_APP_ROOT"
  let policyDir = root </> "keelmark-policy"
      shardRoot = root </> "keelmark-shards"
      outDir = root </> "output"
  rawContract <- loadContract (policyDir </> "pack-contract.json")
  edition <- loadEdition (policyDir </> "edition-policy.json")
  roster <- loadRoster (policyDir </> "block-roster.json")
  (suppress, rawMute) <- loadSuppress (policyDir </> "suppress-blocks.json")
  amendments <- loadAmendments (policyDir </> "amendments.jsonl")
  let (contract, alertMute) = applyAmendments amendments rawContract rawMute
  let rosterMap = Map.fromList [(rName r, r) | r <- roster]
      monitored = Map.fromList [(n, ()) | n <- cMonitored contract]
      pinKeys = ePins edition
      candidates =
        sortBy (comparing id)
          [ n
          | n <- Map.keys rosterMap
          , Map.member n monitored
          , Map.member n pinKeys
          ]
  results <- forM candidates $ \name -> do
    let rb = rosterMap Map.! name
        pin = pinKeys Map.! name
        basePath = shardRoot </> name </> "tension_events.jsonl"
        overlayPath = shardRoot </> name </> "tension_events.overlay.jsonl"
    baseExists <- doesFileExist basePath
    baseRaw <- if baseExists then readFile basePath else pure ""
    overlayExists <- doesFileExist overlayPath
    overlayRaw <- if overlayExists then readFile overlayPath else pure ""
    let joiner = if null baseRaw || last baseRaw == '\n' then "" else "\n"
        raw = baseRaw ++ joiner ++ overlayRaw
        lineCount = countNonBlankLines raw
        (parsed, retracted) = parseTensionEvents raw
        windowed = windowFilter (cWindowStart contract) (cWindowEnd contract) parsed
        deduped = dedupEvents windowed
        escalates = peerEscalates deduped
        winDrop = length parsed - length windowed
        dupDrop = length windowed - length deduped
    pure (name, rb, pin, lineCount, deduped, escalates, winDrop, dupDrop, retracted)

  let abiOk = eEditionAbi edition == cRequiredAbi contract
      suppressSet = Map.fromList [(n, ()) | n <- suppress]
      (deferred, premeasured, eventLines) =
        foldl' (accumulate abiOk suppressSet contract) ([], [], 0) results
      cycleSet = braceCycleMembers premeasured
      cycleDeferred = [DeferredRow n "brace_cycle" | n <- Map.keys cycleSet]
      survivors = [pm | pm <- premeasured, not (Map.member (pmName pm) cycleSet)]
      usableTotal = sum (map pmSamples survivors)
      windowDropped = sum (map pmWinDrop survivors)
      dedupDropped = sum (map pmDupDrop survivors)
      retractedTotal = sum (map pmRetracted survivors)
      deferredSorted = sortBy (comparing drName) (deferred ++ cycleDeferred)
      baseMap = Map.fromList [(pmName pm, pmBaseT pm) | pm <- survivors]
      measured = map (finalizeRow contract baseMap) survivors
      blocksSorted = sortBy blockOrder measured
      muteSet = Map.fromList [(n, ()) | n <- alertMute]
      qualifying =
        [ b
        | b <- blocksSorted
        , brClassification b `elem` ["CRITICAL", "WARN"]
        , brLoadIndex b >= fromIntegral (cMinAlertIndex contract)
        ]
      alertsMuted = length [b | b <- qualifying, Map.member (brName b) muteSet]
      alerts =
        sortBy alertOrder
          [ AlertRow
              { arBlock = brName b
              , arSeverity = brClassification b
              , arMaxKN = brMaxKN b
              , arEffTenths = brEffTenths b
              , arLoadIndex = brLoadIndex b
              , arSampleCount = brSampleCount b
              , arZone = brZone b
              , arSteward = brSteward b
              , arCellClass = brCellClass b
              , arAuditStamp = cAuditStamp contract
              , arContractRevision = cRevision contract
              }
          | b <- qualifying
          , not (Map.member (brName b) muteSet)
          ]
  createDirectoryIfMissing True outDir
  writeReports
    outDir
    (eAuditToken edition)
    (eVersion edition)
    (cRevision contract)
    (ePackageVersion edition)
    blocksSorted
    alerts
    deferredSorted
    eventLines
    usableTotal
    windowDropped
    dedupDropped
    retractedTotal
    alertsMuted

-- Measured block prior to cycle quarantine and the brace-uplift pass.
data Premeasured = Premeasured
  { pmName :: String
  , pmRoster :: RosterBlock
  , pmSamples :: Int
  , pmMaxKN :: Double
  , pmBaseT :: Integer
  , pmPeer :: String
  , pmRawTs :: String
  , pmEscalates :: Bool
  , pmWinDrop :: Int
  , pmDupDrop :: Int
  , pmRetracted :: Int
  }

accumulate
  :: Bool
  -> Map.Map String ()
  -> Contract
  -> ([DeferredRow], [Premeasured], Int)
  -> (String, RosterBlock, String, Int, [TensionEvent], Bool, Int, Int, Int)
  -> ([DeferredRow], [Premeasured], Int)
accumulate abiOk suppressSet contract (defs, blocks, linesAcc) (name, rb, pin, lineCount, events, escalates, winDrop, dupDrop, retracted)
  | Map.member name suppressSet =
      (DeferredRow name "suppress_hit" : defs, blocks, linesAcc + lineCount)
  | not abiOk =
      (DeferredRow name "abi_miss" : defs, blocks, linesAcc + lineCount)
  | pin /= rPackageRev rb =
      (DeferredRow name "pin_mismatch" : defs, blocks, linesAcc + lineCount)
  | null events =
      (DeferredRow name "empty_shard" : defs, blocks, linesAcc + lineCount)
  | otherwise =
      let maxKn = maximum (map teKN events)
          samples = length events
          gain = Map.findWithDefault 1.0 (rCellClass rb) (cGains contract)
          lastEv = selectLastEvent events
          pm =
            Premeasured
              { pmName = name
              , pmRoster = rb
              , pmSamples = samples
              , pmMaxKN = maxKn
              , pmBaseT = effTenths maxKn gain
              , pmPeer = dominantPeer events
              , pmRawTs = teTs lastEv
              , pmEscalates = escalates
              , pmWinDrop = winDrop
              , pmDupDrop = dupDrop
              , pmRetracted = retracted
              }
      in (defs, pm : blocks, linesAcc + lineCount)

-- Vertices on any directed cycle (including self-braces) in the graph
-- restricted to blocks that survived the earlier deferral reasons.
braceCycleMembers :: [Premeasured] -> Map.Map String ()
braceCycleMembers pms =
  let vertices = Map.fromList [(pmName pm, ()) | pm <- pms]
      edges =
        Map.fromList
          [ (pmName pm, [p | p <- rBraces (pmRoster pm), Map.member p vertices])
          | pm <- pms
          ]
      succsOf n = Map.findWithDefault [] n edges
      reachClosure frontier seen
        | null frontier = seen
        | otherwise =
            let nexts = [t | f <- frontier, t <- succsOf f, not (Map.member t seen)]
                seen' = foldl' (\m t -> Map.insert t () m) seen nexts
            in reachClosure nexts seen'
      onCycle n = Map.member n (reachClosure (succsOf n) Map.empty)
  in Map.fromList [(n, ()) | n <- Map.keys vertices, onCycle n]

-- Single-pass brace uplift: partners contribute their pre-uplift base tenths.
finalizeRow :: Contract -> Map.Map String Integer -> Premeasured -> BlockRow
finalizeRow contract baseMap pm =
  let rb = pmRoster pm
      uplift = sum [ b `div` 50 | p <- rBraces rb, Just b <- [Map.lookup p baseMap] ]
      finalT = pmBaseT pm + uplift
      effWarn = Map.findWithDefault (cWarnKN contract) (rZone rb) (cZoneWarn contract)
      klass = classifyBlock effWarn (cCritKN contract) finalT (pmEscalates pm)
      idx = loadIndex finalT (pmSamples pm) (rRated rb)
  in BlockRow
       { brName = pmName pm
       , brZone = rZone rb
       , brCellClass = rCellClass rb
       , brSteward = rSteward rb
       , brSampleCount = pmSamples pm
       , brMaxKN = pmMaxKN pm
       , brEffTenths = finalT
       , brDominantPeer = pmPeer pm
       , brLoadIndex = idx
       , brClassification = klass
       , brLastTensionAt = padTensionTs (pmRawTs pm)
       , brRawTs = pmRawTs pm
       , brPackageRev = rPackageRev rb
       , brContractRevision = cRevision contract
       }

blockOrder :: BlockRow -> BlockRow -> Ordering
blockOrder a b =
  compare (classRank (brClassification a)) (classRank (brClassification b))
    <> compare (brRawTs a) (brRawTs b)
    <> compare (brLoadIndex a) (brLoadIndex b)
    <> compare (brName b) (brName a)
  where
    classRank "CRITICAL" = 0 :: Int
    classRank "WARN" = 1
    classRank _ = 2

alertOrder :: AlertRow -> AlertRow -> Ordering
alertOrder a b =
  compare (sevRank (arSeverity a)) (sevRank (arSeverity b))
    <> compare (arBlock a) (arBlock b)
  where
    sevRank "CRITICAL" = 0 :: Int
    sevRank _ = 1

data Amendment = Amendment
  { amSeq :: Int
  , amStatus :: String
  , amTarget :: String
  , amValue :: Value
  , amSupersedes :: [Int]
  }

loadAmendments :: FilePath -> IO [Amendment]
loadAmendments path = do
  exists <- doesFileExist path
  raw <- if exists then BS.readFile path else pure BS.empty
  pure (mapMaybe parseLine (BS8.lines raw))
  where
    parseLine ln
      | BS.null (BS8.filter (/= ' ') ln) = Nothing
      | otherwise = case eitherDecodeStrict ln of
          Right (Object o) ->
            Just Amendment
              { amSeq = round (mustNum o "seq")
              , amStatus = mustStr o "status"
              , amTarget = mustStr o "target"
              , amValue = fromMaybe Null (KM.lookup "value" o)
              , amSupersedes = mustIntList o "supersedes"
              }
          _ -> Nothing

-- Ratified rows only; a row is void when a higher-seq ratified row supersedes it;
-- survivors apply in ascending seq so later rows overwrite the same target.
applyAmendments :: [Amendment] -> Contract -> [String] -> (Contract, [String])
applyAmendments ams contract mutes =
  let ratified = [a | a <- ams, amStatus a == "ratified"]
      voided s = or [s `elem` amSupersedes a | a <- ratified, amSeq a > s]
      surviving = sortOn amSeq [a | a <- ratified, not (voided (amSeq a))]
  in foldl' applyOne (contract, mutes) surviving
  where
    applyOne (c, ms) a = case (amTarget a, amValue a) of
      ("warn_kN", Number n) -> (c { cWarnKN = fromRational (toRational n) }, ms)
      ("critical_kN", Number n) -> (c { cCritKN = fromRational (toRational n) }, ms)
      ("alert_mute_add", String t) -> (c, ms ++ [T.unpack t])
      (target, Number n)
        | "class_gains." `isPrefixOf` target ->
            let cls = drop (length ("class_gains." :: String)) target
            in (c { cGains = Map.insert cls (fromRational (toRational n)) (cGains c) }, ms)
      _ -> (c, ms)

mustIntList :: KM.KeyMap Value -> Key.Key -> [Int]
mustIntList o k = case KM.lookup k o of
  Just (Array arr) -> [round (fromRational (toRational n) :: Double) | Number n <- foldr (:) [] arr]
  _ -> error ("missing int array " ++ T.unpack (Key.toText k))

loadContract :: FilePath -> IO Contract
loadContract path = do
  bs <- BS.readFile path
  case eitherDecodeStrict bs of
    Right (Object o) -> do
      let win = case KM.lookup "audit_window" o of
                  Just (Object w) -> (mustStr w "start", mustStr w "end")
                  _ -> error "pack-contract: missing audit_window"
          zoneWarn = case KM.lookup "zone_overrides" o of
            Just (Object zs) ->
              Map.fromList
                [ (T.unpack (Key.toText zone), mustNum zo "warn_kN")
                | (zone, Object zo) <- KM.toList zs
                ]
            _ -> Map.empty
      pure Contract
        { cRevision = mustStr o "contract_revision"
        , cAuditStamp = mustStr o "audit_stamp"
        , cRequiredAbi = mustStr o "required_edition_abi"
        , cWarnKN = mustNum o "warn_kN"
        , cCritKN = mustNum o "critical_kN"
        , cMinAlertIndex = round (mustNum o "min_alert_index")
        , cWindowStart = fst win
        , cWindowEnd = snd win
        , cGains = mustNumMap o "class_gains"
        , cZoneWarn = zoneWarn
        , cMonitored = mustStrList o "monitored_blocks"
        }
    Left err -> error ("pack-contract: " ++ err)
    _ -> error "pack-contract: expected object"

loadEdition :: FilePath -> IO Edition
loadEdition path = do
  bs <- BS.readFile path
  case eitherDecodeStrict bs of
    Right (Object o) ->
      pure Edition
        { eVersion = mustStr o "version"
        , eAuditToken = mustStr o "audit_token"
        , ePackageVersion = mustStr o "package_version"
        , eEditionAbi = mustStr o "edition_abi"
        , ePins = mustStrMap o "block_pins"
        }
    Left err -> error ("edition-policy: " ++ err)
    _ -> error "edition-policy: expected object"

loadRoster :: FilePath -> IO [RosterBlock]
loadRoster path = do
  bs <- BS.readFile path
  case eitherDecodeStrict bs of
    Right (Object o) ->
      case KM.lookup "blocks" o of
        Just (Array arr) -> pure (mapMaybe parseRoster (foldr (:) [] arr))
        _ -> error "block-roster: missing blocks"
    Left err -> error ("block-roster: " ++ err)
    _ -> error "block-roster: expected object"
  where
    parseRoster (Object o) =
      Just RosterBlock
        { rName = mustStr o "name"
        , rZone = mustStr o "zone"
        , rCellClass = mustStr o "cell_class"
        , rSteward = mustStr o "steward"
        , rRated = round (mustNum o "rated_tonnage")
        , rPackageRev = mustStr o "package_rev"
        , rBraces = mustStrList o "braces"
        }
    parseRoster _ = Nothing

loadSuppress :: FilePath -> IO ([String], [String])
loadSuppress path = do
  bs <- BS.readFile path
  case eitherDecodeStrict bs of
    Right (Object o) ->
      pure (mustStrList o "names", mustStrList o "alert_mute")
    Left err -> error ("suppress-blocks: " ++ err)
    _ -> error "suppress-blocks: expected object"

mustStr :: KM.KeyMap Value -> Key.Key -> String
mustStr o k = case KM.lookup k o of
  Just (String t) -> T.unpack t
  _ -> error ("missing string field " ++ T.unpack (Key.toText k))

mustNum :: KM.KeyMap Value -> Key.Key -> Double
mustNum o k = case KM.lookup k o of
  Just (Number n) -> fromRational (toRational n)
  _ -> error ("missing number field " ++ T.unpack (Key.toText k))

mustStrList :: KM.KeyMap Value -> Key.Key -> [String]
mustStrList o k = case KM.lookup k o of
  Just (Array arr) ->
    [ T.unpack t | String t <- foldr (:) [] arr ]
  _ -> error ("missing string array " ++ T.unpack (Key.toText k))

mustStrMap :: KM.KeyMap Value -> Key.Key -> Map.Map String String
mustStrMap o k = case KM.lookup k o of
  Just (Object m) ->
    Map.fromList
      [ (T.unpack (Key.toText key), T.unpack val)
      | (key, String val) <- KM.toList m
      ]
  _ -> error ("missing string map " ++ T.unpack (Key.toText k))

mustNumMap :: KM.KeyMap Value -> Key.Key -> Map.Map String Double
mustNumMap o k = case KM.lookup k o of
  Just (Object m) ->
    Map.fromList
      [ (T.unpack (Key.toText key), fromRational (toRational n))
      | (key, Number n) <- KM.toList m
      ]
  _ -> error ("missing number map " ++ T.unpack (Key.toText k))
