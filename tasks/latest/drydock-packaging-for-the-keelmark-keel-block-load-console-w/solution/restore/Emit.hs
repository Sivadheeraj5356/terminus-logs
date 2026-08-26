{-# LANGUAGE CPP #-}

module Keelmark.Emit
  ( writeReports
  ) where

import           Data.Bits      (xor)
import qualified Data.ByteString as BS
import qualified Data.ByteString.Char8 as BS8
import           Data.List      (intercalate, sortBy)
import           Data.Ord       (comparing)
import           Data.Word      (Word64)
import           Keelmark.Types (AlertRow (..), BlockRow (..), DeferredRow (..))
import           System.FilePath ((</>))
import           Text.Printf    (printf)

writeReports
  :: FilePath
  -> String
  -> String
  -> String
  -> String
  -> [BlockRow]
  -> [AlertRow]
  -> [DeferredRow]
  -> Int
  -> Int
  -> Int
  -> Int
  -> Int
  -> Int
  -> IO ()
writeReports outDir auditToken packRev contractRev packageVersion blocks alerts deferred eventLines usableTotal windowDropped dedupDropped retractedTotal alertsMuted = do
  let measured = length blocks
      candidateCount = measured + length deferred
      critical = sortBy (comparing id) [brName b | b <- blocks, brClassification b == "CRITICAL"]
      warn = sortBy (comparing id) [brName b | b <- blocks, brClassification b == "WARN"]
      stable = sortBy (comparing id) [brName b | b <- blocks, brClassification b == "STABLE"]
      inv = encodeInventory auditToken packRev contractRev packageVersion blocks critical warn stable deferred
      invSig = fnv64Hex inv
      al = encodeAlerts alerts
      df = encodeDeferred deferred
      sm = encodeSummary auditToken packRev contractRev packageVersion candidateCount measured (length deferred) eventLines usableTotal windowDropped dedupDropped retractedTotal (length alerts) alertsMuted invSig
      bundleSig = fnv64Hex (inv ++ (al ++ "\n") ++ df ++ (sm ++ "\n"))
      seal = "KEELMARK-GATE|" ++ packRev ++ "|" ++ invSig ++ "|" ++ bundleSig ++ "|" ++ show (length alerts) ++ "|" ++ show alertsMuted
  writeFile (outDir </> "pack_inventory.json") inv
  writeFile (outDir </> "tension_alerts.json") (al ++ "\n")
  writeFile (outDir </> "deferred.json") df
  writeFile (outDir </> "summary.json") (sm ++ "\n")
#ifdef KEELMARK_GATE_V2
  writeFile (outDir </> "gate_seal.txt") (seal ++ "\n\n")
#else
  -- Tide-era seal polarity: a single trailing newline.
  writeFile (outDir </> "gate_seal.txt") (seal ++ "\n")
#endif

-- FNV-1a 64-bit over the exact inventory bytes, 16-char lowercase hex.
fnv64Hex :: String -> String
fnv64Hex s =
  let bytes = BS.unpack (BS8.pack s)
      h = foldl (\acc b -> (acc `xor` fromIntegral b) * 1099511628211) (14695981039346656037 :: Word64) bytes
  in printf "%016x" h

encodeInventory
  :: String -> String -> String -> String
  -> [BlockRow] -> [String] -> [String] -> [String] -> [DeferredRow]
  -> String
encodeInventory auditToken packRev contractRev packageVersion blocks critical warn stable deferred =
  intercalate "\n"
    [ "{"
    , "  \"audit_token\": " ++ jstr auditToken ++ ","
    , "  \"pack_revision\": " ++ jstr packRev ++ ","
    , "  \"contract_revision\": " ++ jstr contractRev ++ ","
    , "  \"package_version\": " ++ jstr packageVersion ++ ","
    , "  \"blocks\": " ++ encodeBlockArray blocks ++ ","
    , "  \"critical\": " ++ encodeStringArray critical ++ ","
    , "  \"warn\": " ++ encodeStringArray warn ++ ","
    , "  \"stable\": " ++ encodeStringArray stable ++ ","
    , "  \"deferred\": " ++ encodeStringArray (map drName deferred)
    , "}"
    ]

encodeAlerts :: [AlertRow] -> String
encodeAlerts alerts =
  intercalate "\n"
    [ "{"
    , "  \"alerts\": " ++ encodeAlertArray alerts
    , "}"
    ]

encodeDeferred :: [DeferredRow] -> String
encodeDeferred rows =
  intercalate "\n"
    [ "{"
    , "  \"deferred\": " ++ encodeDeferredArray rows
    , "}"
    ]

encodeSummary
  :: String -> String -> String -> String
  -> Int -> Int -> Int -> Int -> Int -> Int -> Int -> Int -> Int -> Int -> String
  -> String
encodeSummary auditToken packRev contractRev packageVersion candidateCount measured deferredCount eventLines usableTotal windowDropped dedupDropped retractedTotal alertCount alertsMuted invSig =
  intercalate "\n"
    [ "{"
    , "  \"audit_token\": " ++ jstr auditToken ++ ","
    , "  \"pack_revision\": " ++ jstr packRev ++ ","
    , "  \"contract_revision\": " ++ jstr contractRev ++ ","
    , "  \"package_version\": " ++ jstr packageVersion ++ ","
    , "  \"candidate_count\": " ++ show candidateCount ++ ","
    , "  \"measured_count\": " ++ show measured ++ ","
    , "  \"deferred_count\": " ++ show deferredCount ++ ","
    , "  \"event_lines_total\": " ++ show eventLines ++ ","
    , "  \"usable_events_total\": " ++ show usableTotal ++ ","
    , "  \"window_dropped_total\": " ++ show windowDropped ++ ","
    , "  \"dedup_dropped_total\": " ++ show dedupDropped ++ ","
    , "  \"retracted_total\": " ++ show retractedTotal ++ ","
    , "  \"alert_count\": " ++ show alertCount ++ ","
    , "  \"alerts_muted\": " ++ show alertsMuted ++ ","
    , "  \"coverage_pct\": " ++ coveragePct measured candidateCount ++ ","
    , "  \"inventory_sig\": " ++ jstr invSig
    , "}"
    ]

-- round_half_up_2dp(100 * measured / candidates) emitted with two decimals.
coveragePct :: Int -> Int -> String
coveragePct measured candidates =
  let cents = if candidates == 0
                then 0 :: Integer
                else floor ((10000 * fromIntegral measured :: Double) / fromIntegral candidates + 0.5)
      bare = printf "%.2f" (fromIntegral cents / 100 :: Double)
  in
#ifdef KEELMARK_GATE_V2
      bare
#else
      -- Tide-era locale-safe emission quoted the percentage.
      jstr bare
#endif

encodeBlockArray :: [BlockRow] -> String
encodeBlockArray [] = "[]"
encodeBlockArray rows =
  "[\n" ++ intercalate ",\n" (map encodeBlock rows) ++ "\n  ]"

encodeBlock :: BlockRow -> String
encodeBlock b =
  intercalate "\n"
    [ "    {"
    , "      \"name\": " ++ jstr (brName b) ++ ","
    , "      \"zone\": " ++ jstr (brZone b) ++ ","
    , "      \"cell_class\": " ++ jstr (brCellClass b) ++ ","
    , "      \"steward\": " ++ jstr (brSteward b) ++ ","
    , "      \"sample_count\": " ++ show (brSampleCount b) ++ ","
    , "      \"max_kN\": " ++ encodeNumber (brMaxKN b) ++ ","
    , "      \"eff_max_kN\": " ++ encodeTenths (brEffTenths b) ++ ","
#ifdef KEELMARK_GATE_V2
    , "      \"dominant_peer\": " ++ jstr (brDominantPeer b) ++ ","
    , "      \"load_index\": " ++ show (brLoadIndex b) ++ ","
#else
    -- Tide-era block rows swapped load_index ahead of dominant_peer.
    , "      \"load_index\": " ++ show (brLoadIndex b) ++ ","
    , "      \"dominant_peer\": " ++ jstr (brDominantPeer b) ++ ","
#endif
    , "      \"classification\": " ++ jstr (brClassification b) ++ ","
    , "      \"last_tension_at\": " ++ jstr (brLastTensionAt b) ++ ","
    , "      \"package_rev\": " ++ jstr (brPackageRev b) ++ ","
    , "      \"contract_revision\": " ++ jstr (brContractRevision b)
    , "    }"
    ]

encodeAlertArray :: [AlertRow] -> String
encodeAlertArray [] = "[]"
encodeAlertArray rows =
  "[\n" ++ intercalate ",\n" (map encodeAlert rows) ++ "\n  ]"

encodeAlert :: AlertRow -> String
encodeAlert a =
  intercalate "\n"
    [ "    {"
    , "      \"block\": " ++ jstr (arBlock a) ++ ","
    , "      \"severity\": " ++ jstr (arSeverity a) ++ ","
    , "      \"max_kN\": " ++ encodeNumber (arMaxKN a) ++ ","
    , "      \"eff_max_kN\": " ++ encodeTenths (arEffTenths a) ++ ","
    , "      \"load_index\": " ++ show (arLoadIndex a) ++ ","
    , "      \"sample_count\": " ++ show (arSampleCount a) ++ ","
    , "      \"zone\": " ++ jstr (arZone a) ++ ","
    , "      \"steward\": " ++ jstr (arSteward a) ++ ","
    , "      \"cell_class\": " ++ jstr (arCellClass a) ++ ","
    , "      \"audit_stamp\": " ++ jstr (arAuditStamp a) ++ ","
    , "      \"contract_revision\": " ++ jstr (arContractRevision a)
    , "    }"
    ]

encodeDeferredArray :: [DeferredRow] -> String
encodeDeferredArray [] = "[]"
encodeDeferredArray rows =
  "[\n" ++ intercalate ",\n" (map encodeDeferredRow rows) ++ "\n  ]"

encodeDeferredRow :: DeferredRow -> String
encodeDeferredRow d =
  intercalate "\n"
    [ "    {"
    , "      \"name\": " ++ jstr (drName d) ++ ","
    , "      \"reason\": " ++ jstr (drReason d)
    , "    }"
    ]

encodeStringArray :: [String] -> String
encodeStringArray [] = "[]"
encodeStringArray xs =
  "[\n" ++ intercalate ",\n" ["    " ++ jstr x | x <- xs] ++ "\n  ]"

jstr :: String -> String
jstr s = "\"" ++ escape s ++ "\""
  where
    escape = concatMap esc
    esc '"' = "\\\""
    esc '\\' = "\\\\"
    esc c = [c]

encodeTenths :: Integer -> String
encodeTenths t = printf "%.1f" (fromIntegral t / 10 :: Double)

encodeNumber :: Double -> String
encodeNumber n =
  let rounded = fromIntegral (round n :: Integer) :: Double
  in if abs (n - rounded) < 1e-12
       then printf "%.1f" n
       else printf "%g" n
