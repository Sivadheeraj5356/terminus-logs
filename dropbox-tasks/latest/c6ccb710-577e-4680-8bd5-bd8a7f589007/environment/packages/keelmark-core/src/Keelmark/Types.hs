{-# LANGUAGE OverloadedStrings #-}

module Keelmark.Types
  ( Contract (..)
  , Edition (..)
  , RosterBlock (..)
  , TensionEvent (..)
  , BlockRow (..)
  , AlertRow (..)
  , DeferredRow (..)
  ) where

import qualified Data.Map.Strict as Map

data Contract = Contract
  { cRevision :: String
  , cAuditStamp :: String
  , cRequiredAbi :: String
  , cWarnKN :: Double
  , cCritKN :: Double
  , cMinAlertIndex :: Int
  , cWindowStart :: String
  , cWindowEnd :: String
  , cGains :: Map.Map String Double
  , cZoneWarn :: Map.Map String Double
  , cMonitored :: [String]
  } deriving (Show)

data Edition = Edition
  { eVersion :: String
  , eAuditToken :: String
  , ePackageVersion :: String
  , eEditionAbi :: String
  , ePins :: Map.Map String String
  } deriving (Show)

data RosterBlock = RosterBlock
  { rName :: String
  , rZone :: String
  , rCellClass :: String
  , rSteward :: String
  , rRated :: Int
  , rPackageRev :: String
  , rBraces :: [String]
  } deriving (Show)

data TensionEvent = TensionEvent
  { teTs :: String
  , teKN :: Double
  , tePeer :: String
  , teKind :: String
  } deriving (Show)

data BlockRow = BlockRow
  { brName :: String
  , brZone :: String
  , brCellClass :: String
  , brSteward :: String
  , brSampleCount :: Int
  , brMaxKN :: Double
  , brEffTenths :: Integer
  , brDominantPeer :: String
  , brLoadIndex :: Integer
  , brClassification :: String
  , brLastTensionAt :: String
  , brRawTs :: String
  , brPackageRev :: String
  , brContractRevision :: String
  } deriving (Show)

data AlertRow = AlertRow
  { arBlock :: String
  , arSeverity :: String
  , arMaxKN :: Double
  , arEffTenths :: Integer
  , arLoadIndex :: Integer
  , arSampleCount :: Int
  , arZone :: String
  , arSteward :: String
  , arCellClass :: String
  , arAuditStamp :: String
  , arContractRevision :: String
  } deriving (Show)

data DeferredRow = DeferredRow
  { drName :: String
  , drReason :: String
  } deriving (Show)
