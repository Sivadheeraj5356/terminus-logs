module Main where

import Data.Char (isSpace)
import Data.List (intercalate, nub, sort, sortBy)
import Data.Maybe (fromMaybe)
import System.Environment (getArgs)
import System.Exit (die)

type Lit = Int
type Clause = [Lit]

data Cnf = Cnf Int [Clause] deriving (Show)
data Mapping = Mapping Int [Lit] [Int] [(Int, Bool, [Clause])] deriving (Show)

main :: IO ()
main = do
  args <- getArgs
  case args of
    [inp, "--out", outp, "--log", logp, "--map", mapp] -> runSimplify inp outp logp mapp
    ["--extend", inp, "--map", mapp, "--model", modelp, "--model-out", outp] -> runExtend inp mapp modelp outp
    _ -> die "usage: cnfprep INPUT --out OUT --log LOG --map MAP | cnfprep --extend INPUT --map MAP --model MODEL --model-out OUT"

runSimplify :: FilePath -> FilePath -> FilePath -> FilePath -> IO ()
runSimplify inp outp logp mapp = do
  Cnf n cls0 <- parseCnf <$> readFile inp
  let normalized = mapMaybeSimple cleanClause cls0
      (cls1, fixed1, events1) = oneSweep normalized [] []
      cls2 = dropSubsumed cls1
      remaining = sort . nub $ map abs (concat cls2)
      mp = Mapping n fixed1 remaining []
      logLines = ["input " ++ show i ++ " " ++ unwords (map show c) ++ " 0" | (i,c) <- zip [(1::Int)..] cls0]
              ++ events1
              ++ ["emit " ++ unwords (map show c) ++ " 0" | c <- cls2]
  writeFile outp (renderCnf n cls2)
  writeFile logp (unlines logLines)
  writeFile mapp (renderMap mp)

runExtend :: FilePath -> FilePath -> FilePath -> FilePath -> IO ()
runExtend inp mapp modelp outp = do
  Cnf n cls <- parseCnf <$> readFile inp
  Mapping _ fixed _ _ <- parseMap <$> readFile mapp
  partial <- readModel <$> readFile modelp
  let base = normalizeModel (partial ++ [(abs l, l > 0) | l <- fixed])
      full = [(v, fromMaybe False (lookup v base)) | v <- [1..n]]
  if satAll full cls then writeFile outp (renderModel full) else die "model does not extend"

oneSweep :: [Clause] -> [Lit] -> [String] -> ([Clause], [Lit], [String])
oneSweep cls fixed ev =
  case [l | [l] <- cls] of
    (l:_) -> let cls' = applyLit l cls in oneSweep cls' (l:fixed) (("assign " ++ show l):ev)
    [] -> let lits = concat cls
              pures = [l | l <- nub lits, negate l `notElem` lits]
          in case pures of
               (l:_) -> (applyLit l cls, l:fixed, ("assign " ++ show l):ev)
               [] -> (cls, reverse fixed, reverse ev)

applyLit :: Lit -> [Clause] -> [Clause]
applyLit l = map (filter (/= negate l)) . filter (notElem l)

dropSubsumed :: [Clause] -> [Clause]
dropSubsumed cls = [c | c <- cls, not (any (properSubset c) cls)]
  where properSubset c d = c /= d && all (`elem` c) d

cleanClause :: Clause -> Maybe Clause
cleanClause c =
  let xs = sortBy litOrd (nub (filter (/=0) c))
  in if any (\l -> negate l `elem` xs) xs then Nothing else Just xs

litOrd :: Lit -> Lit -> Ordering
litOrd a b = compare (abs a, a < 0) (abs b, b < 0)

parseCnf :: String -> Cnf
parseCnf s =
  let ls = filter (not . null) (map words (lines s))
      body = [ws | ws <- ls, head ws /= "c"]
      header = [ws | ws <- body, take 1 ws == ["p"]]
      n = case header of { (["p","cnf",nv,_]:_) -> read nv; _ -> 0 }
      nums = concatMap (map read) [ws | ws <- body, take 1 ws /= ["p"]]
  in Cnf n (splitClauses nums)

splitClauses :: [Int] -> [Clause]
splitClauses [] = []
splitClauses xs = let (a,b) = break (==0) xs in a : splitClauses (drop 1 b)

renderCnf :: Int -> [Clause] -> String
renderCnf n cls = unlines $ ("p cnf " ++ show n ++ " " ++ show (length cls)) : map (\c -> unwords (map show c ++ ["0"])) cls

renderMap :: Mapping -> String
renderMap (Mapping n fixed remaining steps) = unlines $ ["n " ++ show n] ++ map (\l -> "f " ++ show l) fixed ++ map (\v -> "r " ++ show v) remaining ++ map renderStep steps

renderStep :: (Int, Bool, [Clause]) -> String
renderStep (v, d, cs) = "e " ++ show v ++ " " ++ (if d then "1 " else "0 ") ++ intercalate " | " (map (unwords . map show) cs)

parseMap :: String -> Mapping
parseMap s = Mapping n fixed remaining []
  where rows = map words (lines s)
        n = case [read x | ["n", x] <- rows] of { (x:_) -> x; _ -> 0 }
        fixed = [read x | ["f", x] <- rows]
        remaining = [read x | ["r", x] <- rows]

readModel :: String -> [(Int, Bool)]
readModel = map one . filter (not . null) . lines
  where one line = let (a,b) = break (=='=') (filter (not . isSpace) line) in (read a, drop 1 b `elem` ["1","true","True"])

renderModel :: [(Int, Bool)] -> String
renderModel xs = unlines [show v ++ "=" ++ if b then "1" else "0" | (v,b) <- xs]

normalizeModel :: [(Int, Bool)] -> [(Int, Bool)]
normalizeModel = foldr add []
  where add (v,b) acc = (v,b) : filter ((/=v) . fst) acc

satAll :: [(Int, Bool)] -> [Clause] -> Bool
satAll m = all (any litSat)
  where litSat l = lookup (abs l) m == Just (l > 0)

mapMaybeSimple :: (a -> Maybe b) -> [a] -> [b]
mapMaybeSimple _ [] = []
mapMaybeSimple f (x:xs) = case f x of Nothing -> mapMaybeSimple f xs; Just y -> y : mapMaybeSimple f xs
