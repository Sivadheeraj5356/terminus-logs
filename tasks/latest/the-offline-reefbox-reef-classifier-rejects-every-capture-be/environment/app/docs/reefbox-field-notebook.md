# ReefBox Field Operations Notebook

## Front matter, how to read this notebook, and glossary

If you are reading this, you have probably just been handed a laptop, a stack of microSD cards pulled out of a salt-crusted housing, and a vague instruction to "build the manifest for the run." Welcome. This notebook is the closest thing we have to institutional memory for the ReefBox program, and it is going to save you a week of pain, but only if you read it the way it is meant to be read. Please slow down for the next few pages. They are not filler.

This is an **append-mostly** document. We started it as a shared scratch file during the first deployment season and it has grown, more or less by accretion, into the de facto operations manual for the whole imaging pipeline. We did not go back and rewrite the old entries when we learned something new, because (a) we never had time, and (b) the old entries are themselves useful as a record of what we believed and why we believed it. So what you are holding is roughly chronological: onboarding notes near the front, then a long sediment of incident reports (we tag them `INC-####`), errata (`ERRATA-###`, always dated), postmortems (`PM-####`), FAQ answers, and the occasional 2 a.m. journal entry written from the back of a boat. It reads like what it is — a logbook kept by busy people — not like a clean specification. The rules you need are in here, but they are scattered through prose, war stories, and worked examples, and you will have to assemble them.

### The single most important rule: later entries win

I am going to state this once, in bold, near the top, because every single onboarding disaster we have had traces back to somebody ignoring it.

**When a later dated entry contradicts an earlier one, the later entry wins. Trust the errata, not the cheat-sheet.**

That is the reading convention. Internalize it. The early pages of this notebook contain advice that we now know is *wrong* — not maliciously wrong, just first-draft wrong, written before we had benched the hardware properly or before a firmware bug was understood. We have deliberately left that wrong advice in place rather than scrubbing it, partly because erasing history makes it impossible to understand later corrections, and partly because half of you will have memorized the old cheat-sheet from a colleague before you ever open this file, and we need you to be able to *find* the correction when it bites you.

So: when you find two statements that disagree, do not average them, do not pick the one that sounds more confident, and do not pick the one you read first. **Find the dates. The later one is operative.** An `ERRATA-###` or a `PM-####` dated last spring overrides a chirpy onboarding note from two seasons ago, full stop, even if the onboarding note is longer and has a nice diagram and the errata is two grumpy sentences. Especially then. The grumpy two-sentence errata is grumpy precisely because somebody got burned.

If you take nothing else from this section, take that. The rest is detail.

### The scene: an offline classifier

Here is what we are actually doing, so the rest of the notebook has somewhere to land.

A ReefBox is a battery-powered camera in a pressure housing that we bolt to a frame and drop on the seafloor. It sits there for weeks taking stills of whatever swims, drifts, or grows in front of it. We do not have a cable or a radio link to most of these units — the deep ones are completely dark until a diver or an ROV brings the housing back up. So everything is **offline**. We recover the housing, pull the storage, and copy off a pile of PNG captures. Days or weeks after the photons actually hit the sensor, those PNGs get fed through an **image classifier** running on our own machines, on shore, in a batch job. There is no live inference, no cloud round-trip at capture time, no human in the loop deciding exposure. The camera shot what it shot; our job downstream is to interpret it correctly after the fact.

"Correctly" is doing a lot of work in that sentence, and it is the reason this notebook exists. A raw ReefBox PNG is not directly usable by the classifier. The pixels coming off these sensors are not in a tidy, calibrated, human-friendly color space. Each individual camera has its own white balance, its own black levels, its own quirks of which physical sensor slot maps to which spectral channel, and — for one unfortunate hardware revision — its own outright defects. Before the classifier sees an image we have to **calibrate** it: figure out, per camera and per capture, how to turn the stored channel values into the canonical channels the model was trained on. Get that wrong and the model still happily returns predictions; they are just quietly garbage. There is no exception thrown when you feed a model a green-and-red-swapped image. It just gives you confident nonsense. That failure mode — silent, plausible-looking wrongness — is the thing this whole document is organized to prevent.

To make calibration possible, every ReefBox embeds a **calibration block** inside each PNG it writes. That block is the heart of the pipeline, and decoding it correctly is most of the battle. The rest of this section introduces it gently. Later sections take it apart byte by byte.

### Where the calibration lives: two metadata keys

The calibration block is carried inside the PNG itself, in a `tEXt` chunk — one of the standard textual-metadata chunks the PNG format allows. You can pull these out with any half-decent image tool; they are just keyword/value pairs riding along inside the file.

There are **two** metadata keys you may encounter, and the distinction matters:

- **`reefbox:calibration`** — written by 2.x ("modern") firmware. When present, this is the **authoritative** block. This is the one you want.
- **`rbx:cal`** — written by legacy 1.x firmware. This is a **fallback only**. If a camera is old enough that it only ever wrote `rbx:cal`, fine, we use it — the internal byte layout is the same — but it is not the preferred source.

You will, unfortunately, run into PNGs that carry **both** keys. There was a bad production batch of 2.x units with a firmware defect we have come to call the "double-write": the new firmware wrote its proper `reefbox:calibration` block but also left a stale `rbx:cal` block lying around from the legacy code path. **When both keys are present, the `reefbox:calibration` (2.x) block wins and the leftover `rbx:cal` block is ignored.** Do not try to reconcile them, do not cross-check one against the other, do not panic if they disagree — the 2.x block is the truth and the legacy block is debris. Just take the 2.x block and move on.

And if **neither** key is present? Then there is nothing to calibrate against, and that capture cannot be used. We have a specific handling path for that (it is not "silently drop it" — see the quarantine discussion much later), but for now just register that "no calibration key at all" is a real, distinct condition we track.

### The value is not text — it's base64 of a packed binary blob

Here is the first place newcomers stub their toes, so I want to flag it loudly even before we get into the gory details.

The **value** sitting under that `tEXt` key looks, at a glance, like a meaningless string of letters and digits and the occasional `+`, `/`, or `=`. It is *tempting* to treat it as text and try to read fields out of it directly. Do not. **The value is base64.** And when you base64-decode it, you do **not** get text either — you get a **packed binary blob**. A little structured record, laid out as raw bytes, that we have to parse field by field.

So the decode is two stages, every time:

1. Take the string value from the `tEXt` chunk.
2. Base64-decode it to get a sequence of raw bytes.
3. Parse those bytes according to the calibration block layout.

A few orienting facts about that binary blob, so you know what you are looking at when you first hex-dump one (the full offset-by-offset breakdown lives in a later section — I am deliberately *not* dumping the whole table here, because half the point of this notebook is that you learn the layout from worked examples, not from one tidy schema you can cargo-cult without understanding):

- It starts with a two-byte **magic** marker, the ASCII letters **"RB"**. If the first two bytes are not "RB", you are either looking at the wrong thing, a corrupt blob, or you base64-decoded something that was never a calibration block. The magic is your sanity check that you are even in the right place.
- Right after the magic there is a **version byte** distinguishing legacy from modern. Reassuringly, the *byte layout itself is identical* across versions — the version byte tells you provenance, not a different parsing scheme. So once you can parse one, you can parse both.
- There is a **flags byte** early in the block. This single byte is densely packed: it encodes the sensor variant *and* a set of per-channel normalization flags, all bit-packed together. We will pick this byte apart bit by bit later; for now just know that one little byte carries several independent decisions, so you cannot eyeball it.
- All multi-byte integers in the blob are **big-endian**. Write that on a sticky note. The number of hours lost to little-endian assumptions in this program is not something I want to put in writing.
- The blob ends with a trailing **CRC** — a checksum computed over everything in front of it. It is there so that a corrupted or truncated block announces itself instead of quietly feeding you bad numbers. If the CRC you recompute does not match the one stored in the trailer, the block is not trustworthy and the capture does not go into the run. (Again: there is a specific handling path for that; not silent dropping.)

That is the shape of it. Magic, version, flags, a body of numeric calibration fields, a device id and a site id, and a CRC to tie a bow on it. The next several sections turn each of those into exact byte offsets, exact integer encodings, and exact arithmetic. Resist the urge to skip ahead and guess; the fields are small and the encodings are fiddly, and a wrong guess produces output that *looks* fine.

### Glossary of the decoded calibration fields

Once you have base64-decoded the value and parsed the binary, you recover a handful of named fields. You will see these abbreviations everywhere in the notebook, in incident reports and in the worked examples, so here is the running glossary. Memorize the names; the exact encodings come later.

- **`dev`** — the **device id**. A short identifier for the physical camera that took the capture, stored as text inside the blob. Every ReefBox has one. The device id is how we tie a capture back to a specific unit, and (spoiler for a later section) it is also how we detect when the same camera somehow contributed two captures to one run and we have to decide which one to keep.

- **`site`** — the **site id**, also stored as text inside the blob. This is where the camera was deployed — a named survey location like `site-lagoon` or `site-pinnacle`. The site is enormously important downstream: it is the key that tells us which inference settings apply (different sites have different mount geometry, different model tuning, and so on). Crucially, the site id also has to be a site we actually *recognize*. We keep a registry of legitimate site names (see "the allowed_sites registry" below), and a capture claiming a site that is not on that list is a red flag, not something to wave through.

- **`sv`** — the **sensor variant**. ReefBox has shipped on more than one sensor board, and they are not interchangeable in how their stored slots map to spectral channels. The sensor variant comes out of the packed flags byte and tells you *which physical board* you are dealing with. This single value drives the channel mapping, and one variant is bad enough that captures from it are unusable. Treat `sv` as one of the most consequential fields in the whole block — getting it wrong silently swaps your channels.

- **`seq`** — the **sequence number**, a 16-bit integer. Think of it as a monotonically increasing counter the camera stamps on its output. Its main job in this pipeline is dedup arbitration: when two captures claim the same device id, the sequence number is the tiebreaker — higher means newer/winner. You will see `seq` used exactly that way in the deduplication discussion.

- **`wb`** — the **white-balance** triple, three per-slot values. These are the core color-correction multipliers. They are stored in the blob as small fixed-point integers rather than as floats (the exact fixed-point convention and the divisor are spelled out later — do not assume they are already-scaled floats when you read the raw bytes). There is one `wb` value per stored slot, and they feed directly into the per-channel scale computation.

- **`blk`** — the **black-level** triple, three per-slot values. These represent the sensor's dark floor — the value a slot reads when it should be reading "zero light." They are small integers, one per slot, and they participate in the scale computation *but only under certain normalization conditions*. Whether a given slot's black level actually affects its scale depends on that slot's normalization flag (next entry). Do not assume `blk` is always applied; sometimes it is, sometimes it is ignored, and the `nz` flags are what decide.

- **`nz`** — the three **normalization flags**, one per stored slot, packed into the flags byte alongside the sensor variant. Each `nz` flag is a single bit that says whether that slot's data was stored "normalized" or "raw." This flag is the switch that determines *how* you combine `wb` and `blk` into a scale for that slot: a normalized slot folds in the black level, a raw slot does not. The three `nz` bits are independent — a single capture can have some slots normalized and others raw. Read all three.

- **`co`** — the **channel-order** triple. Now, `co` deserves a careful word, and this is where I am going to be honest with you about the state of our understanding.

### A careful (perhaps too generous) word about `co`

`co` is a three-value triple stored in the calibration block that, on its face, looks like it tells you the channel ordering for the capture — which stored slot corresponds to which output channel. The name practically screams "channel order." And early in the program, that is exactly how several of us read it. There are onboarding notes (further down) that treat `co` as a first-class input to the channel mapping, and there are worked examples that consult it. If you have been taught the pipeline informally, you may well have been told that `co` is how you decide which slot feeds red, green, and NIR.

I am including `co` in the glossary, and describing it generously here, precisely because you *will* encounter it prominently in the older material and you need to recognize it. The triple is real, it is in every block, it sits right alongside `wb` and `blk` in the layout, and it certainly *looks* load-bearing. On a first read of this notebook you could be forgiven for thinking the entire channel-mapping question routes through `co`.

But — and here is where the reading convention earns its keep — **there is a later errata about `co`.** Please go find it before you rely on this field for anything. I am not going to restate its conclusion here, because the whole disciplinary point of this notebook is that you learn to chase the dates and let the later entry win rather than trusting whatever the front matter happened to assert. What I will say is: the status of `co` was revisited after we benched the hardware more carefully, and what the early notes say about it does not survive that revisit unchanged. So treat the glossary entry you are reading right now as the *early, generous* characterization — "`co` looks like it might decide channel order" — and treat the later dated errata as the operative word on the subject. **See later errata** before you let `co` touch your output.

(If that feels like an unsatisfying way to document a field, good. That feeling is the reading convention working on you. Hold onto the discomfort and go read the dated entries.)

### The downstream inference settings and the `allowed_sites` registry

Decoding the calibration block tells you how to fix up the *pixels*. It does not, by itself, tell you which *model* to run or with what parameters. Those inference settings come from a separate layer of YAML configuration that lives alongside the pipeline — a global baseline plus per-site and per-device overrides. The full precedence rules (which layer wins for which setting, and the several exceptions where the "obvious" precedence does *not* apply) are their own substantial topic and get their own section. For front-matter purposes, just know that the model card and its parameters are *not* baked into the PNG; they are looked up, by site and by device, from configuration after decoding.

One piece of that configuration deserves a name-drop here because it connects directly to the `site` field above. The **global** configuration carries an **`allowed_sites`** list — this is the **registry of recognized sites**. It is the canonical roster of survey locations we accept. When a decoded `site` field comes out of a calibration block, it gets checked against `allowed_sites`. A site that is on the registry is a real deployment we can attribute and configure; a site that is *not* on the registry is something we cannot trust — a typo, a test unit, a misconfiguration, a camera that wandered somewhere it should not have — and it does not get to flow through as if it were a normal capture. The registry is small and curated and lives in the global config precisely so there is one obvious place to look when a capture's site looks unfamiliar. (As an aside, you may occasionally see an obviously fake placeholder like `site-ghost` used in examples specifically to *illustrate* an unrecognized site; that is on purpose, to show the not-on-the-registry path.)

### How the pieces fit (a deliberately incomplete map)

Let me draw the rough flow once, so the later sections have a skeleton to hang on. I am being deliberately incomplete — this is orientation, not the spec.

1. **Recover and copy.** PNGs come off recovered storage and land in a working directory. The filename of each capture matters later (the downstream manifest refers to captures by their bare filename, never a path-prefixed one), so do not rename them casually.
2. **Find the calibration.** For each PNG, look in the `tEXt` chunks for `reefbox:calibration` first, then `rbx:cal`. Modern beats legacy; if both are there because of the double-write batch, the modern `reefbox:calibration` wins and the legacy one is ignored; if neither is there, the capture has no calibration at all.
3. **Decode.** Base64-decode the chosen value, check the "RB" magic, parse the binary, and verify the trailing CRC over everything before it. A bad magic, an unparseable body, or a CRC mismatch means the block is not trustworthy.
4. **Interpret.** From the parsed fields, read the sensor variant out of the flags byte, work out the channel mapping, and compute per-channel scales from `wb`, `blk`, and the `nz` flags. (And remember the careful word about `co` — chase the errata.)
5. **Attribute and configure.** Use the decoded `site` — checked against `allowed_sites` — and the decoded `dev` to look up inference settings from the layered YAML, respecting the precedence rules and their exceptions.
6. **Deduplicate.** Where the same `dev` shows up more than once, keep the highest `seq` and set the others aside.
7. **Emit, or set aside.** Good captures go into the downstream manifest with their channel scales and inference settings. Captures that failed any of the gates along the way are *not* silently dropped — they are set aside with a recorded reason. The full set of reasons, and the strict order in which they are evaluated, is its own section. For now just absorb the principle: **nothing disappears silently; everything that does not make the run has a recorded reason.**

Every one of those steps has sharp edges, and almost every sharp edge is documented downstream as an incident we actually hit. Read the incidents. They are not anecdotes for color; each one encodes a rule.

### A short note on the examples in this notebook

To protect real deployments and real hardware, the device ids, site names, and model names used in the worked examples throughout this notebook are **fictional**. If you see a device id like `RBX-7A2C`, a site like `site-lagoon` or `site-pinnacle`, or a model name like `reefnet-coastal`, those are illustrative stand-ins chosen so we can show real mechanics without leaking the real fleet roster. When we show byte-level detail, the hex dumps are likewise small, made-up blobs constructed to make a point. Do not go looking for `RBX-7A2C` in the asset database; it does not exist. The *mechanics* the examples demonstrate are real and exact; the *identifiers* are invented. Keep that distinction in mind, especially when you are pattern-matching an example against a real capture in front of you — match the structure and the arithmetic, not the literal names.

### Before you go further

A last bit of orientation etiquette, learned the hard way:

- **Read chronologically the first time.** Yes, you can grep for the answer to your specific question, and once you know this notebook you will. But on your first pass, read front-to-back, because the corrections only make sense if you have seen the mistakes they correct. The "wrong then fixed" structure is a feature.
- **When in doubt, find the date.** Two statements disagree? Date them. Later wins.
- **Trust the errata, not the cheat-sheet.** Somebody's tidy summary — including, occasionally, parts of this very front matter — may be the *earlier*, superseded view. The dated `ERRATA-###` and `PM-####` entries are where the program's actual hard-won conclusions live.
- **Nothing is dropped silently.** If a capture can't go in, it goes in the set-aside pile with a reason. We will get rigorous about exactly which reasons and in what order; the principle starts now.

With all of that in hand, turn the page. The next sections get specific — the byte layout of the calibration block, the bit-packing of that flags byte, the sensor variants and their channel mappings, the scale arithmetic, deduplication, the YAML precedence rules and their exceptions, and the structure of the manifest we ultimately emit. The detail is coming. The discipline — *later entries win, trust the errata* — starts here.
## Quick Reference Card (v1.0 — superseded, see errata)

> Pin this above your desk. It's everything you need to go from a ReefBox PNG to a
> ready-to-infer manifest entry in under five minutes. Written up after the first
> two weeks on the rig so nobody else has to re-learn it the hard way. — fieldeng

Okay. You just pulled a stack of captures off a ReefBox and you need to turn the
calibration metadata into channel scales and a manifest row. This card is the
fast path. If you only read one page in this notebook, read this one. Everything
here has been confirmed against the units we have on the bench right now
(RBX-7A2C, RBX-22E9, a couple of the older 1.x boxes), so it's not theory — it's
what actually came off the wire.

### 30-second version

1. Pop the tEXt chunk out of the PNG.
2. Base64-decode the value. You get back the old `key=value` calibration text.
3. Read the fields you care about (white balance, black level, the channel order).
4. Apply white balance, read channels straight through, done.
5. Merge in the YAML model card (device card wins), write the manifest row.

That's the whole loop. The rest of this card is just spelling out each step so a
new hire can do it without bugging anyone.

### Step 1 — Find the calibration in the PNG

Cameras stash the calibration in a PNG `tEXt` chunk. There are two possible keys:

- `reefbox:calibration` — written by the 2.x firmware boxes.
- `rbx:cal` — the original 1.x key.

Most of our fleet is still 1.x, so in practice you'll see `rbx:cal` most of the
time. A handful of the 2.x boxes got flashed with a buggy build that writes BOTH
keys into the same PNG ("double-write" units — you'll know them, they're the ones
with the green dot on the housing). When you see both keys, **keep the `rbx:cal`
block**. The legacy key is the one that's been stable across every firmware we've
shipped; the `reefbox:calibration` block on those double-write boxes is the one
that came out half-baked, so don't trust it. Original key wins. Easy rule:
*"when in doubt, rbx:cal it out."*

If neither key is present, the capture has no calibration and you can't process
it. Set it aside (see quarantine below).

### Step 2 — Decode the value (it's just base64 text)

Here's the part that trips people up at first, so let me be crystal clear: the
tEXt value **looks** like garbage, but it is **not** binary. It is plain base64,
and when you decode it you get back the original calibration string — the same
`key=value` lines the firmware used internally before it got base64-wrapped for
transport. They wrap it so the `=` and newlines don't upset the PNG chunk parser,
that's all. Nothing fancy.

So your decode is literally:

```
raw_text = base64_decode(text_chunk_value)
```

and `raw_text` will look something like:

```
ver=1;seq=5;wb=10342,9988,10500;blk=2,1,3;order=0,1,2;dev=RBX-7A2C;site=site-lagoon;sum=...
```

Don't overthink it. If you see something that doesn't look like readable text
after base64-decoding, you almost certainly grabbed the wrong chunk or the PNG is
truncated — re-pull it.

> Pro tip: `base64 -d` on the command line, then eyeball it. If it's readable,
> you're good. If it's not, the file's bad.

### Step 3 — The fields

Parse the decoded `key=value` text. The fields you'll see, in roughly the order
the firmware lays them out:

| field    | meaning                                  | notes                          |
|----------|------------------------------------------|--------------------------------|
| `ver`    | format version (1 = legacy, 2 = modern)  | layout is the same either way  |
| `flags`  | packed bits — variant + normalization    | see below                      |
| `seq`    | capture sequence number                  | used for dedup                 |
| `wb`     | three white-balance multipliers          | **stored ×1000** (see note)    |
| `blk`    | three black-level offsets (0..15)        | per channel                    |
| `order`  | channel order triple                     | **use this as the order!**     |
| `dev`    | device id string                         | e.g. `RBX-7A2C`                |
| `site`   | site id string                           | e.g. `site-lagoon`             |
| `sum`    | trailing checksum                        | 8-bit sum of the bytes         |

A few of these need spelling out.

**White balance is stored times 1000.** The firmware doesn't ship floats, it
ships integers. To recover the real multiplier you divide by 1000. So if you read
`wb=10342,9988,10500`, the actual multipliers are:

```
wb[0] = 10342 / 1000 = 10.342
wb[1] =  9988 / 1000 =  9.988
wb[2] = 10500 / 1000 = 10.500
```

(Yes, ~10× multipliers look big, but these are linear sensor units, not display
gains. Trust the math.) Divide by a thousand, move on.

**Black level** (`blk`) is three small integers, one per channel, each in the
range 0..15. You'll use these in the normalized-scale formula below.

**The flags byte** packs a couple of things. Low two bits are the sensor variant
(0 = A, 1 = B, 2 = C). The next three bits are normalization flags, one per
channel — bit 2 is channel 0, bit 3 is channel 1, bit 4 is channel 2. If a
channel's normalization bit is set, that channel was captured "normalized" and you
apply the black-level correction; if it's clear, the channel is raw and you just
use the white balance straight. (Formula's in Step 4.)

**The order triple** (`order`) tells you which stored slot feeds which output
channel. This is the important one and it's the thing people get wrong, so commit
it to memory: **the `order` triple IS the channel order.** Read it and map your
slots accordingly. Don't go inventing per-variant mappings — the camera already
told you the order, just use what it gave you.

### Step 4 — Endianness and the numbers (read this once, carefully)

For the raw-bytes folks: if you ever decide to skip the `key=value` view and read
the packed numeric form directly (some of the tooling does this for speed), all
multi-byte integers are **little-endian**. The low byte comes first. So a `seq`
that reads `05 00` on the wire is `0x0005` = 5, and `wb` value bytes `66 28` is
`0x2866` = 10342. Little-endian throughout — that's how the firmware's host CPU
laid them out, and they didn't byte-swap on the way out. If your `seq` values come
back looking enormous (like tens of thousands when you expected single digits),
you read it big-endian by mistake. Flip it.

Quick gut-check table for the little-endian read:

```
bytes on wire   ->  value
00 01           ->  0x0100 = 256        (NOT 1)
05 00           ->  0x0005 = 5
66 28           ->  0x2866 = 10342
```

### Step 5 — The checksum (it's just a byte sum)

The last field is an integrity check. It's simple: it's the **8-bit sum of all the
preceding bytes**, taken mod 256. To verify a capture, add up every byte before
the checksum, mask to 8 bits, and compare against the stored `sum`. If they match,
the capture's good. If they don't, it's corrupt — quarantine it.

```
running = 0
for b in all_bytes_before_sum:
    running = (running + b) & 0xFF
assert running == stored_sum
```

That's it. No polynomial tables, no fancy CRC business — just a rolling 8-bit add.
Whoever spec'd the firmware kept it dead simple, bless them. (If you've worked with
other gear that uses real CRCs, resist the urge to over-engineer this. It's a sum.)

### Step 6 — Sensor variants & channel mapping (straight through)

Canonical output order is always RED, GREEN, NIR. And here's the good news that
makes this whole job easy: **every variant reads straight through.**

```
slot0 -> RED
slot1 -> GREEN
slot2 -> NIR
```

That's true for variant A, variant B, all of them. The "variant" bits in the flags
byte are basically informational — different board revisions, same wiring order on
the output side. So you do **not** need a lookup table of per-variant slot
mappings. Whoever told you variant B is wired differently was looking at a
prototype; the production boards all landed on the same straight-through order.

And remember from Step 3: if you want to be extra careful, the `order` triple in
the metadata confirms it for you. Read `order`, it'll say `0,1,2`, and that's your
RED/GREEN/NIR slot assignment. Use the `order` triple as the authoritative channel
order and you literally cannot get this wrong.

So in practice the mapping step is a no-op. RED is slot 0, GREEN is slot 1, NIR is
slot 2, every time.

### Step 7 — Per-channel scale

Now the actual numbers the classifier wants. For each output channel, look at its
stored slot `s` (which, per Step 6, is just 0/1/2 for RED/GREEN/NIR):

- If channel `s` is **normalized** (its nz bit is set):
  ```
  scale = wb[s] * (255 - blk[s]) / 255
  ```
- If channel `s` is **raw** (its nz bit is clear):
  ```
  scale = wb[s]
  ```

Round every scale to 6 decimal places. (Remember `wb[s]` here is already the
divided-by-1000 value from Step 2.)

Worked example with the values from earlier (`wb=10342,9988,10500` ->
`10.342, 9.988, 10.500`; `blk=2,1,3`; say all three channels normalized):

```
RED   (slot0): 10.342 * (255 - 2) / 255 = 10.342 * 0.992157 = 10.260863
GREEN (slot1):  9.988 * (255 - 1) / 255 =  9.988 * 0.996078 =  9.948831
NIR   (slot2): 10.500 * (255 - 3) / 255 = 10.500 * 0.988235 = 10.376471
```

Round to 6 dp and those are your `channel_scales`.

### Step 8 — Dedup

Sometimes two captures carry the same `dev`. Keep the one with the **highest
`seq`**; the older same-device captures get set aside (quarantined as
"superseded"). One device, one winning row.

### Step 9 — Model card / YAML precedence

Inference settings come from three YAML layers:

- `global.yaml` — baseline defaults, plus the `allowed_sites` registry.
- `sites/<site>.yaml` — per-site overrides (site comes from the decoded `site`
  field).
- `devices/<dev>.yaml` — per-device overrides.

Precedence is simple and uniform: **the device card always wins.** For every
field — `model_name`, `model_version`, `input_size`, `confidence_threshold`,
`labels_version` — if there's a device-level value, use it. If not, fall back to
the site value, and if that's missing, the global value. Device beats site beats
global, across the board, no exceptions. One rule for all fields; don't memorize
special cases.

```
value = device.field ?? site.field ?? global.field
```

### Step 10 — Quarantine

Don't ever silently drop a capture. If something's off, it goes in the quarantine
list with a reason. There are **three** reasons you'll hit:

- `missing_calibration` — neither calibration key was present in the PNG.
- `sensor_variant_c` — the capture came off a variant C board.
- `superseded` — it lost the same-device dedup (an older `seq`).

That's the full set. Pick the first one that applies, tag the capture, move on.

### Step 11 — Write the manifest row

Once you've got scales + model card, emit the manifest entry. Top-level manifest is
`manifest_version` `"1.0"`, `channel_order` `["RED","GREEN","NIR"]`, then a
`devices` array (sorted by `device_id`) and a `quarantined` array, plus a `summary`.

Each device row carries: `device_id`, `site`, `source_png` (the bare capture
filename — no path prefix, just e.g. `rbx-7a2c-0005.png`), `sensor_variant` (raw
letter, `"A"`/`"B"`), `channel_scales` `{RED, GREEN, NIR}` rounded to 6 dp,
`model_name`, `model_version`, `input_size` `[w, h]`, `confidence_threshold`, and
`labels_version`.

Illustrative fragment (do not copy the numbers, they're made up):

```json
{
  "device_id": "RBX-7A2C",
  "site": "site-lagoon",
  "source_png": "rbx-7a2c-0005.png",
  "sensor_variant": "A",
  "channel_scales": { "RED": 10.260863, "GREEN": 9.948831, "NIR": 10.376471 },
  "model_name": "reefnet-coastal",
  "model_version": "3.2.0",
  "input_size": [512, 512],
  "confidence_threshold": 0.41,
  "labels_version": "2026-01-15"
}
```

The `quarantined` array is a list of `{ source_png, reason }`, sorted by
`source_png`. The `summary` is just `{ included, quarantined }` counts.

### The whole thing on one breath

> Pull the tEXt chunk. If both keys, keep `rbx:cal`. Base64-decode to get the old
> `key=value` text. Read fields little-endian if you go binary. `wb` is ÷1000.
> Verify the trailing 8-bit byte-sum. Read channels straight through (slot0=RED,
> slot1=GREEN, slot2=NIR), or just trust the `order` triple. Apply
> `wb*(255-blk)/255` for normalized channels, `wb` for raw, round to 6 dp. Highest
> `seq` wins per device. Device card wins every field. Three quarantine reasons:
> missing_calibration, sensor_variant_c, superseded.

Tape it to the wall. You'll have it memorized by the end of your first rotation.

### Worked end-to-end example (do this once and it'll click)

Let's run a whole capture through, start to finish, so the loop is concrete. Say
you pulled `rbx-7a2c-0005.png` off the box this morning and you want its manifest
row.

First, the tEXt chunk. You crack the PNG and find an `rbx:cal` key (no
`reefbox:calibration` on this one — it's a 1.x box). Grab the value. Base64-decode
it. Out comes:

```
ver=1;flags=28;seq=5;wb=10342,9988,10500;blk=2,1,3;order=0,1,2;dev=RBX-7A2C;site=site-lagoon;sum=...
```

Readable text — good, the file's clean. Now the fields:

- `ver=1` — legacy box, layout's the same as 2.x anyway, don't care.
- `flags=28` — that's `0b11100` in binary. Low two bits are `00`, so **variant A**.
  Bits 2/3/4 are all set (`111`), so all three channels are **normalized**.
- `seq=5` — hold onto this for dedup.
- `wb=10342,9988,10500` — divide each by 1000: `10.342, 9.988, 10.500`.
- `blk=2,1,3` — black levels per channel.
- `order=0,1,2` — straight through, exactly as expected. RED<-slot0, GREEN<-slot1,
  NIR<-slot2. (You didn't even need this since everything's straight-through, but
  it's nice to see the camera agree with you.)
- `dev=RBX-7A2C`, `site=site-lagoon` — for the manifest row.

Verify the checksum: sum every byte before `sum`, mask to 8 bits, compare. Matches
-> proceed.

Now the scales. All three channels normalized, so each uses
`wb[s]*(255-blk[s])/255`:

```
RED:   10.342 * (255-2)/255 = 10.260863
GREEN:  9.988 * (255-1)/255 =  9.948831
NIR:   10.500 * (255-3)/255 = 10.376471
```

Round to 6 dp. Check the site — `site-lagoon` is in `global.yaml`'s
`allowed_sites`, so it's recognized. Pull the model card: device card
`devices/RBX-7A2C.yaml` exists and sets `model_version: 3.2.0`, so that wins over
whatever site or global said. Same logic for every other field. Assemble the row
and you're done. Total time, once you've got the tooling: about a minute.

### Common failure modes (and what they usually mean)

A few things you'll hit in the first month, and the quick read on each:

- **Decoded value looks like binary noise, not text.** You grabbed the wrong chunk
  (PNGs have several tEXt chunks sometimes) or the file's truncated. Re-pull. Don't
  try to "parse the noise" — the value is base64 of readable text, full stop.
- **`seq` comes back as a giant number.** You read it big-endian. These are
  little-endian; flip the byte order.
- **`wb` multipliers look 10× too big or too small.** Double-check you divided by
  1000, not 100 or 10000. It's a thousand.
- **Checksum mismatch on a file you trust.** Make sure you're summing *all*
  preceding bytes and masking to 8 bits each step. If you're computing some CRC
  with a polynomial, stop — it's a plain byte sum, and a CRC routine will "fail"
  every clean file.
- **Channels look swapped in the output (e.g. NIR where RED should be).** This
  basically shouldn't happen with straight-through mapping. If it does, the file's
  probably corrupt or you mis-read the slots. Don't start hand-building per-variant
  remaps — that's a rabbit hole and the production boards don't need it.

### Cheat-sheet of the cheat-sheet (the literal field card)

This is the laminated card we actually keep in the dry box. Reproduced here so
it's searchable:

```
REEFBOX -> MANIFEST  (v1.0)
1. tEXt chunk -> value. Both keys? keep rbx:cal.
2. base64-decode -> key=value text.
3. fields: ver flags seq wb blk order dev site sum
4. ints little-endian.  wb / 1000.
5. checksum = 8-bit byte sum, mod 256.
6. channels straight through: slot0=R slot1=G slot2=NIR (order triple confirms).
7. norm channel: wb*(255-blk)/255 ; raw: wb ; round 6dp.
8. dedup: highest seq wins.
9. YAML: device > site > global, every field.
10. quarantine: missing_calibration | sensor_variant_c | superseded.
```

If you've got that card and a base64 decoder, you can field-process a whole stack
of captures off one ReefBox without opening this notebook again. Which is the
point — the notebook is for the weird cases; this card is for the other 95%.

### A note on speed vs. correctness

Look, this card is optimized for getting boats unblocked, not for being a spec. We
wrote it fast because the survey schedule didn't wait for us to fully understand
the format. It matches everything we've seen so far and it'll get you a manifest
that loads. If you ever hit a capture where the scales come out looking obviously
wrong — channels swapped, numbers off by an order of magnitude, checksums failing
on files you're pretty sure are clean — don't fight this card. Flag it, write it
up as an incident, and check whether someone's posted an erratum that supersedes a
step here.

---

*Footer / housekeeping: This is the v1.0 quick reference, written early in the
program before we'd torn the format all the way down. It's been good enough for
day-to-day work, but it is a cheat sheet, not gospel — a few of the steps here were
written from the firmware folks' verbal description rather than from the bytes
themselves. If a later dated ERRATA or postmortem in this notebook contradicts
something on this card, the later entry wins. Trust the errata, not the
cheat-sheet. Superseded; retained for history.*
## Hardware overview: the three sensor variants

This section is the one we keep sending new hires to before they touch a single
capture. If you only read one thing about ReefBox optics, read this — and then go
read the errata, because at least one paragraph below used to be wrong and somebody
*will* trip over the old version in an archived PDF somewhere. (Reading convention,
again, for the people in the back: this notebook is append-mostly and roughly
chronological. When a later dated note contradicts an earlier one, the later note
wins. Trust the errata, not the cheat-sheet.)

Let me set the stage. ReefBox is an undersea camera. It sits in a pressure housing,
stares at a reef, and every so often it grabs a frame. That frame goes nowhere near
a human in real time — it gets pulled off the unit during a service dive (or over
the acoustic link if we're lucky and the link is up), and then it feeds an offline
image classifier back on the boat / back on shore. The classifier cares a lot about
color, because half of what we're separating — coral bleaching, algal cover,
substrate type — is a color-and-texture problem. So the *photometric* side of the
camera matters as much as the lens. Get the channels wrong and the classifier
confidently tells you a healthy stand of Acropora is bleached. We have done this.
There is an incident report. We'll get there in a later section.

The thing to internalize up front: **there are three hardware variants of the
optical stack**, they are NOT interchangeable, and the differences are not cosmetic.
Variant determines *which physical photosite feeds which output channel*. Get the
variant wrong and you have effectively swapped your red and near-infrared planes,
which is about the worst silent failure this system has, because the image still
*looks* like an image. It just lies.

### The optical stack, briefly

Mechanically all three variants share the same outer housing, the same dome port,
the same O-ring groove (thank goodness — we only stock one size of spare), and the
same image sensor *package*. What differs is the filter mosaic and, on one variant,
the *wiring* between the photosites and the readout slots. ReefBox is not an RGB
camera in the consumer sense. It captures three bands that we care about:

- **RED** — visible red, roughly the deep-water-penetrating end of what's left of
  the visible spectrum once you're a few meters down.
- **GREEN** — visible green, the band that survives best underwater and does most of
  the heavy lifting for the classifier.
- **NIR** — near-infrared. Useless for "pretty pictures" (NIR doesn't propagate far
  in water at all), but the photosite is there because the same sensor die is used
  in a terrestrial product line, and it turns out the NIR plane is a great
  glare/specular-highlight discriminator at very short range. Don't ask why marketing
  shipped it; just know it's a real channel and the manifest expects it.

The **canonical output order is always RED, GREEN, NIR**. That ordering never
changes. It is baked into the downstream manifest (`channel_order` is literally
`["RED","GREEN","NIR"]` in every manifest we emit), it is what the classifier's
input tensor expects, and it is the order you should think in. The whole *point* of
the variant logic is to take whatever physical arrangement a given board has and
present it back as RED, GREEN, NIR in that order.

Internally the sensor exposes three **stored slots**: slot0, slot1, slot2. Think of
these as "the first, second, and third planes as they physically come off the
readout." The slots are dumb. They have no idea what color they are. They're just
slot0, slot1, slot2 — three buckets of pixel data in a fixed physical order. The
*mapping* from slot to canonical channel is the entire game, and that mapping is a
**property of the variant**. Same slots on every unit; different meaning per variant.

### Where the variant comes from

You do not guess the variant, you do not read it off a sticker, and — critically —
you do NOT infer it from the debug channel-order triple in the calibration block.
(There's a `co[0..2]` triple in there. It is a debug artifact. Skip those three
bytes. Never use them to decide channel mapping. More than one well-meaning engineer
has "helpfully" decoded `co` and used it; it is noise as far as production is
concerned.)

The variant is encoded in the **flags byte** of the calibration block — that's
byte 3 of the decoded binary blob, for those following along with the byte layout.
Specifically, **the low two bits (bits 0 and 1) of the flags byte encode the sensor
variant**:

- `0` → Variant A
- `1` → Variant B
- `2` → Variant C

(Value `3` is not assigned to a shipping variant; if you ever see it, treat the block
as suspect and let the integrity checks deal with it. We've never seen one in the
field, but never say never with the cost-down boards.)

So the decode order in your head is: pull the flags byte, mask off the low two bits,
that integer *is* the variant, and the variant *alone* tells you the slot→channel
mapping. The other bits of the flags byte do other things — bits 2, 3, and 4 are the
three normalization flags `nz[0]`, `nz[1]`, `nz[2]` — but for *this* section we only
care about the variant in the bottom two bits. The mapping is a function of the
variant and nothing else. Not `co`. Not the device id. Not which site it came from.
The variant.

A small concrete example so the bit-masking isn't abstract. Say you've decoded a
block and the flags byte is `0x0D`. In binary that's `0000 1101`. The low two bits
are `01` = 1, so this is **Variant B**. (Bits 2 and 3 are also set, so `nz[0]=1` and
`nz[1]=1`, but that's the normalization story, not the variant story.) Another:
flags byte `0x10` = `0001 0000`. Low two bits are `00` = 0 → **Variant A**, with
`nz[2]=1`. And `0x06` = `0000 0110`: low two bits `10` = 2 → **Variant C**, and at
that point you stop caring about the rest because Variant C captures are unusable
(see below). Mask, read two bits, done.

### Variant A — straight-through

Variant A is the original board and the one we wish everything were. It is
"straight-through": the photosites are wired to the slots in the obvious order, and
the filter mosaic puts the colors where you'd expect. So:

- **slot0 = RED**
- **slot1 = GREEN**
- **slot2 = NIR**

Which means RED comes from slot0, GREEN from slot1, NIR from slot2. No transposition,
no surprises. If every unit in the fleet were Variant A this whole section would be
two sentences long. When you read a Variant A block, you take slot0's data, call it
RED, take slot1, call it GREEN, take slot2, call it NIR, and move on to the
per-channel scaling.

Most of our oldest, most reliable units are Variant A. They're heavier, they draw
more power, and we can't get the boards anymore, but the ones still running are the
ones we trust without a second thought on the optics side. The map is the identity
map. slot index == channel index in canonical order.

### Variant B — the cost-down board, and the mapping everyone gets wrong

Variant B is where the pain lives, so read this part twice.

Variant B is the "cost-down" board. At some point the supplier re-laid-out the
sensor interconnect to save money, and in doing so they **wired the NIR photosite
into the FIRST stored slot**. That is the single fact that everything else hangs off
of: on Variant B, **slot0 is NIR**. Not RED. NIR. The plane that comes off the
readout first is the near-infrared plane, because that's how the cheaper board is
physically wired.

That alone would be manageable — you'd just know "slot0 is NIR on B" and pull RED and
GREEN from slots 1 and 2. The trouble is *which* of slot1 and slot2 is RED and which
is GREEN, and this is precisely the bit that an earlier version of this very notebook
got **wrong**.

Here is the **current truth**, from the latest re-bench (this supersedes anything you
read earlier):

- **slot0 = NIR**
- **slot1 = GREEN**
- **slot2 = RED**

Equivalently, stated in canonical channel order, which is how you should actually
wire your code:

- **RED comes from slot2**
- **GREEN comes from slot1**
- **NIR comes from slot0**

Say it out loud: on Variant B, **RED is slot2, GREEN is slot1, NIR is slot0.** The
visible channels are *transposed* relative to A, and the NIR sits up front. That's
the whole mapping.

#### The correction — why this paragraph exists

Now the war story, because you need to know this so you don't "fix" the code back to
the broken version when you find the old note.

When Variant B first showed up, somebody bench-characterized it in a hurry and wrote
down that the NIR photosite went to slot0 (correct) and then recorded the two visible
channels as **RED at slot1, GREEN at slot2**. That earlier write-up had RED and GREEN
**swapped**. It read, in effect, "slot0=NIR, slot1=RED, slot2=GREEN." That was wrong.

The re-bench — a more careful one, with an actual reference target instead of "eh,
the red ball looks red-ish" — transposed the two visible channels and established
that it is the other way around: the GREEN photosite lands in slot1 and the RED
photosite lands in slot2. So the corrected, current mapping is **slot0=NIR,
slot1=GREEN, slot2=RED**, i.e. RED from slot2 and GREEN from slot1, as stated above.

If you are reading an older internal doc, an archived onboarding PDF, or a stray
comment in some retired script, and it says Variant B is "RED at slot1, GREEN at
slot2" — **that is the superseded version. Do not use it.** The later entry wins.
RED is slot2. GREEN is slot1. I am repeating this on purpose because the swap is
exactly the kind of thing that looks plausible and produces images that almost look
right, so it survives a casual eyeball. It does not survive a color target, and it
absolutely does not survive the classifier, which will quietly start mis-scoring
red-dominant scenes.

#### Why the swap is so dangerous

A red↔green swap on the *visible* channels is subtle in a way that a red↔NIR swap is
not. NIR underwater is mostly dark, so if you accidentally feed NIR into RED you tend
to get an obviously wrong, weirdly dim red plane and someone notices. But green and
red planes underwater both carry real, plausible-looking signal. Swap them and you
get an image that is *wrong but believable*. The histogram looks fine. The thumbnail
looks fine. And then the classifier — which learned that "lots of red relative to
green" means one thing and "lots of green relative to red" means another — starts
flipping its calls. That is the failure mode the re-bench was chasing down, and it's
why we now treat the Variant B mapping as a thing you memorize rather than something
you eyeball.

A tiny worked sketch to make it concrete. Suppose a Variant B unit gives you, in
slot order, three planes I'll label by their *stored slot*:

```
slot0:  [ NIR data ]   <- this is near-infrared, even though it came off first
slot1:  [ GREEN data ]
slot2:  [ RED data ]
```

To assemble the canonical RED, GREEN, NIR output you reach across like this:

```
canonical RED   <- slot2
canonical GREEN <- slot1
canonical NIR   <- slot0
```

Notice GREEN happens to stay put at slot1 — that's a coincidence of the layout, not a
rule, and it's part of why the old swapped version was easy to half-believe. RED and
NIR are the ones that move relative to "obvious." Don't pattern-match on "green didn't
move so the rest is probably fine."

#### A note on why it's wired this way

You don't need this to do the job, but it helps it stick. The cost-down interconnect
routed the photosite that needed the shortest, cleanest trace (the NIR site, which on
this die sits physically nearest the readout tap) into slot0, and then the two
visible photosites filled in behind it. The order the two visibles ended up in
(green before red) was an accident of the routing, not a deliberate choice, which is
*also* why the first person to characterize the board guessed wrong — there was no
intuitive "of course it's this way" to lean on. There wasn't a logic to recover; you
just have to know it. slot0=NIR, slot1=GREEN, slot2=RED.

### Variant C — defective, unusable

Variant C is the easy one to handle and the saddest one to own. It was a defective
lens batch. The optical element itself is bad — there's a delamination / coating
problem in the dome-side group that introduces a wandering chromatic smear that we
cannot calibrate out. It's not a wiring issue and it's not a filter issue; the glass
is wrong. No slot→channel mapping can save it because the light is already corrupted
before it ever reaches the photosites.

So the rule for Variant C is blunt: **captures from a Variant C unit are unusable.**
There is no mapping table for C. You do not try to assemble RED/GREEN/NIR. You do not
attempt scaling. The moment you decode the variant and see it's C (low two bits of
the flags byte == `2`), the capture is done — it gets quarantined with the
`sensor_variant_c` reason and you move on. We keep the units around because the
housings and electronics are fine and we cannibalize them for spares, but no Variant
C *image* should ever reach the classifier.

(Operational aside: a handful of Variant C units were redeployed with replacement
optics from the A line during a refit, and *those* were re-flashed so they report as
Variant A in the flags byte, which is correct because after the optics swap they
genuinely are straight-through. The point being: trust the flags byte, not the
serial number or the deployment history. If the flags byte says C, it's C, full
stop, and it's `sensor_variant_c`.)

### Putting the mapping in one place

Here's the whole slot→channel story on one screen. Memorize the A row and the B row;
the C row is "don't."

```
Variant  flags low2bits   slot0    slot1    slot2     => canonical assembly
-------  -------------    -----    -----    -----        ---------------------------
  A           0           RED      GREEN    NIR          RED<-slot0 GREEN<-slot1 NIR<-slot2
  B           1           NIR      GREEN    RED          RED<-slot2 GREEN<-slot1 NIR<-slot0
  C           2           ---      ---      ---          UNUSABLE: quarantine sensor_variant_c
```

Read that B row carefully one more time. **slot0 is NIR. slot2 is RED.** If your
memory of this table ever drifts back toward "B has RED in slot1," stop, come back
here, and re-read the correction above. That drift is the single most common mistake
on this whole pipeline.

### Things people get wrong (collected, so you don't add to the list)

- **Using `co` to decide the mapping.** No. The debug channel-order triple is
  ignored entirely. The *variant* decides the mapping, and the variant comes from the
  low two bits of the flags byte. Skip `co`.
- **Reverting Variant B to the old RED@slot1/GREEN@slot2.** This is the superseded
  mapping. The re-bench corrected it to RED@slot2/GREEN@slot1. Later entry wins.
- **Treating slots as if they "know" their color.** They don't. slot0/1/2 are just
  physical readout order. Color meaning is assigned *per variant*.
- **Trying to salvage a Variant C frame.** Don't. There is nothing to salvage; the
  glass is bad. Quarantine it.
- **Inferring variant from the device id, the site, or the deployment log.** The unit
  may have been re-flashed (see the C→A refit note). The flags byte is authoritative
  for what the hardware *currently is*.
- **Assuming GREEN moving (or not) tells you something.** On both A and B, GREEN
  happens to live at slot1. That's coincidence, not a rule you can lean on to sanity-
  check the others. RED and NIR are the channels that actually move between variants.

### A short field log, because mappings stick better as stories

Pulling a few entries out of the dive logs, lightly cleaned up, because the abstract
table never sticks the way an actual screw-up does.

**Entry, early deployment season.** Swapped a tired old straight-through unit on the
shallow transect for one of the new lighter boards. Didn't think twice — same
housing, same port, dropped right in. First batch of frames came back and the green
looked oddly muted relative to what we remembered from the same spot. Chalked it up
to turbidity. It was not turbidity. It was the first Variant B unit any of us had
handled, and we were still assembling RED/GREEN/NIR as if it were straight-through.
We were pulling RED from slot0 — which on a B board is *NIR* — so the "red" plane was
basically the dark near-infrared plane and the actual red was sitting unused in
slot2. Lesson burned in: a lighter board is not necessarily a Variant A board. Decode
the flags byte. Read the variant. Don't assume from the chassis.

**Entry, a few weeks later.** Once we knew Variant B existed we wrote the first
mapping note — and that's the one that had RED at slot1 and GREEN at slot2. For a
little while the images looked *better* than the straight-through-assumption disaster,
which made everyone relax, because at least now NIR was correctly coming off slot0 and
the visibles were no longer being read as infrared. But "better than catastrophically
wrong" is not "right." The classifier scores on a couple of red-heavy substrate sites
kept drifting in a way nobody could explain from the environment.

**Entry, the re-bench.** We finally put a unit on the bench with a proper color
reference instead of trusting our eyes on reef footage. Lit a target with known
red/green/NIR response and read out the three slots. slot0 lit up for the NIR source
(good, that part was right all along). But the slot that lit for the *red* source was
slot2, and the slot that lit for *green* was slot1 — the exact opposite of what the
first note claimed. That settled it. The earlier note had the two visible channels
transposed. Corrected mapping: slot0=NIR, slot1=GREEN, slot2=RED. RED from slot2,
GREEN from slot1, NIR from slot0. We re-ran the affected sites and the score drift
vanished. This entry is the authority; the earlier note is dead.

**Entry, the C refit.** Separately, the bad-glass batch (Variant C) finally got dealt
with. A few of those units came back to the shop, got fresh A-line optics, and were
re-flashed so their flags byte reports Variant A. They are Variant A now and they read
correctly as straight-through. Anything still reporting C in the flags byte is still
defective and still gets `sensor_variant_c`. The serial number tells you the unit's
history; the flags byte tells you what it *is* right now. Use the flags byte.

### Quick decision flow for a single capture (optics only)

When a frame lands on your desk and you're reasoning about the *optical* side and
nothing else, the variant logic collapses to a tiny decision flow:

1. Decode the calibration block; grab the flags byte (byte 3).
2. Mask the low two bits: `variant_code = flags & 0x03`.
3. Branch on `variant_code`:
   - `0` → Variant A. Assemble RED←slot0, GREEN←slot1, NIR←slot2.
   - `1` → Variant B. Assemble RED←slot2, GREEN←slot1, NIR←slot0.
   - `2` → Variant C. Stop. Quarantine `sensor_variant_c`. No assembly.
4. Hand the assembled-in-canonical-order planes off to the scaling stage (separate
   section).

Three branches. Two of them are a mapping; the third is a hard stop. If you find
yourself writing a fourth branch, or reaching for `co`, or pulling the variant from
anywhere other than the low two bits of the flags byte, back up — you've wandered off
the canon.

One more bit-masking reminder, because it's the most mechanical part and therefore
the easiest to fat-finger: it is the **low** two bits. `flags & 0x03`. Not the high
bits, not bits 2–4 (those are the `nz[0]`/`nz[1]`/`nz[2]` normalization flags and
belong to the scaling section), not some shifted version. Mask with `0x03`, compare
the result to 0/1/2. A flags byte of `0xFE` (`1111 1110`) is variant `10` = 2 = C,
no matter how busy the rest of the byte looks. A flags byte of `0xFD` (`1111 1101`)
is variant `01` = 1 = B. The upper bits are someone else's problem.

### What this section does NOT cover

To keep the lane clean: this section is *only* about which physical slot feeds which
canonical channel, which is purely a function of the variant. It does **not** tell
you how to *scale* those channels — the white-balance, the black-level subtraction,
and the per-channel normalization flags all live in their own section, and they
operate *after* you've assembled the correct slot→channel mapping. It also doesn't
cover how the variant byte sits inside the larger calibration block, how that block
is base64-decoded and CRC-checked, or how we choose between the two metadata keys
when a unit double-wrote both. Those are separate stories. Here, the takeaway is
exactly three rows of a table:

- **A: straight through.** slot0=RED, slot1=GREEN, slot2=NIR.
- **B: cost-down, NIR up front, visibles transposed.** slot0=NIR, slot1=GREEN,
  slot2=RED → RED from slot2, GREEN from slot1, NIR from slot0. (Earlier note had
  RED/GREEN swapped; corrected by re-bench; the corrected mapping is current truth.)
- **C: defective optics, unusable.** No mapping; quarantine as `sensor_variant_c`.

And the variant itself? Low two bits of the flags byte. Every time. Nothing else
gets a vote.
## The calibration block: PNG keys, base64, and the packed binary layout

OK. This is the section everybody bookmarks and nobody reads carefully enough the
first time, so I'm going to be tediously explicit. If you are new and you only read
one part of this notebook before touching the pipeline, read THIS one and section 5
(the CRC). Everything downstream — the channel scaling, the model-card lookups, the
manifest we hand to the inference box — is built on top of correctly pulling apart
this little blob. Get the blob wrong and you get confidently-wrong numbers, which is
worse than a crash. A crash you notice.

Quick orientation before the gory details. Every ReefBox capture is a PNG. Inside the
PNG, alongside the actual pixels, the firmware stashes a small calibration record in a
`tEXt` chunk — that's the standard PNG "textual data" chunk, a keyword plus a value.
We do NOT touch the image pixels in this stage at all. We only care about that text
chunk. The value of the chunk is base64. Decode the base64 and you get a packed binary
blob — a fixed header, a couple of variable-length strings, and a checksum on the end.
That blob is the calibration block, and reverse-engineering its byte layout is the
whole game here.

### Which PNG key do I read?

There are two keywords that can show up in the `tEXt` chunk, and which one you trust
depends on which one is present:

- `reefbox:calibration` — written by firmware 2.x. This is the **authoritative** one.
  When you see it, this is your block. Full stop.
- `rbx:cal` — written by the legacy 1.x firmware. This is a **fallback only**. Read it
  only if there is no 2.x key.

The good news, and the thing that trips people up because it sounds like it should be
harder than it is: the byte layout inside the value is *identical* between 1.x and 2.x.
Same magic, same header, same everything. The only structural difference is the
`version` byte (byte 2) reads `1` vs `2`. So you do NOT need two parsers. You need one
parser and a rule about which key to feed it.

The rule:

1. If `reefbox:calibration` is present, decode and parse THAT. Ignore `rbx:cal`
   entirely even if it's sitting right there.
2. Else if `rbx:cal` is present, decode and parse that.
3. Else — neither key present — the capture is `missing_calibration`. (Quarantine; see
   the quarantine section for the full reason-code ladder. Don't try to be clever and
   reconstruct calibration from a sibling file or a filename. If the keys aren't there,
   it's missing, period.)

#### The "double-write" units (why rule 1 is so blunt)

You'd think a 2.x camera would only ever write the 2.x key. Mostly true. But we had a
bad manufacturing/flash batch — the field name for it is the **double-write** batch —
where 2.x units wrote BOTH keys into the same PNG. The `reefbox:calibration` block and
a leftover `rbx:cal` block, both sitting in the same file.

This caused a genuinely nasty class of bug early on, because the two blocks weren't
always byte-for-byte the same. The legacy `rbx:cal` block on those units is **stale** —
it's a snapshot from an older calibration pass, sometimes with a different seq, occasionally
even a slightly different white-balance triple. If you happened to read `rbx:cal` first
(some early scripts iterated chunks in file order and grabbed the first match), you'd
silently calibrate against months-old numbers and never know.

So the rule is deliberately unconditional and dead simple:

> **When both keys are present, the `reefbox:calibration` (2.x) block WINS and the
> `rbx:cal` block is ignored.** Do not diff them. Do not "merge." Do not warn-and-pick.
> 2.x present → 2.x wins. The leftover `rbx:cal` is treated as if it weren't there.

I cannot stress this enough because it *feels* wrong to throw away data you can see. You
are not throwing away good data; you are throwing away stale data that a buggy firmware
batch left behind. Trust the 2.x key.

A corollary people forget: this precedence is purely about *which key you read*. It is
NOT a fallback-on-failure thing. If `reefbox:calibration` is present but its block is
corrupt (bad magic, won't decode, CRC fails), you do **not** then fall back to `rbx:cal`.
The 2.x key was chosen; if the chosen block is bad, the capture is `bad_checksum`. We
chose the block, we live with the block. (Corrupt-block handling proper lives in the
quarantine + firmware-errata sections — I'm only flagging the interaction here so nobody
writes a "well, the modern one failed, let me try the legacy one" branch. We tried that
in 2.x-era tooling and it masked real corruption. Don't.)

### From PNG text to bytes: the base64 step

The `tEXt` value is **base64**. This surprises newcomers because PNG `tEXt` is nominally
"textual data" and people expect to read it with their eyes. You can't. It looks like
line noise. That's expected — it's base64 of binary.

So the pipeline for the value is always:

```
PNG tEXt value  --(base64 decode)-->  raw bytes  --(parse layout below)-->  calibration block
```

Standard base64. Decode it to a byte string. Then parse the bytes. If the base64 itself
won't decode, that's a corrupt block and you're heading for `bad_checksum` — but again,
that's the quarantine section's problem, not this section's. Here I'm assuming you've
got clean bytes in hand and I'm telling you what they mean.

One small practical note from the field: do not let your YAML/JSON tooling "helpfully"
re-wrap, trim, or re-encode the value before you decode it. We had an incident where a
pretty-printer inserted whitespace into the base64 and a strict decoder choked. Read the
chunk value verbatim, decode verbatim.

### The packed binary layout (THE table)

Decode the base64 and you have a byte sequence. Here is the full layout. **Every
multi-byte integer in this blob is BIG-ENDIAN.** Burn that into your brain; it's the #1
mistake (the #2 mistake is the fixed-point divide, covered right after). I'll list every
offset:

| Offset | Size | Field | Meaning |
|-------:|-----:|-------|---------|
| 0–1 | 2 | `magic` | The two ASCII bytes `"RB"` → `0x52 0x42`. |
| 2 | 1 | `version` | `1` = legacy (1.x), `2` = modern (2.x). Layout identical regardless. |
| 3 | 1 | `flags` | Bit-packed. See below. |
| 4–5 | 2 | `seq` | uint16, big-endian. Sequence number (used for dedup). |
| 6–7 | 2 | `wb[0]` | uint16 fixed-point = round(wb * 10000). |
| 8–9 | 2 | `wb[1]` | uint16 fixed-point = round(wb * 10000). |
| 10–11 | 2 | `wb[2]` | uint16 fixed-point = round(wb * 10000). |
| 12 | 1 | `blk[0]` | uint8, range 0..15. |
| 13 | 1 | `blk[1]` | uint8, range 0..15. |
| 14 | 1 | `blk[2]` | uint8, range 0..15. |
| 15 | 1 | `co[0]` | uint8. **DEBUG channel-order triple — SKIP.** |
| 16 | 1 | `co[1]` | uint8. **DEBUG — SKIP.** |
| 17 | 1 | `co[2]` | uint8. **DEBUG — SKIP.** |
| 18 | 1 | `dev_len` | uint8. Length in bytes of the device-id string that follows. |
| 19 .. 19+dev_len-1 | `dev_len` | `dev` | ASCII device id. |
| (next) | 1 | `site_len` | uint8. Length in bytes of the site-id string that follows. |
| (next) .. | `site_len` | `site` | ASCII site id. |
| last 2 | 2 | `crc16` | uint16, big-endian. CRC-16 over EVERY preceding byte. |

That's it. Fixed 18-byte header (offsets 0–17), then `dev_len` + dev, then `site_len` +
site, then the 2-byte CRC trailer. The total length of the blob is therefore
`18 + 1 + dev_len + 1 + site_len + 2` bytes. There is no padding, no alignment, no
length prefix for the whole record. The two length-prefixed strings are the only variable
part.

#### Byte 3, the flags, in detail

The flags byte packs four things into the low five bits. (High bits are reserved / don't
care — don't assert on them; firmware has set stray high bits before and the data was
still fine.)

- **Bits 0–1** (the low two bits, value 0–3): **sensor variant.**
  - `0` → Variant **A**
  - `1` → Variant **B**
  - `2` → Variant **C**
  - (`3` we've never seen in the wild; treat as unknown/garbage if it ever appears.)
- **Bit 2** → `nz[0]` (normalization flag for stored slot 0)
- **Bit 3** → `nz[1]` (normalization flag for stored slot 1)
- **Bit 4** → `nz[2]` (normalization flag for stored slot 2)

So `variant = flags & 0x03`, `nz[0] = (flags >> 2) & 1`, `nz[1] = (flags >> 3) & 1`,
`nz[2] = (flags >> 4) & 1`. The variant decides channel mapping; the nz flags decide
whether each slot's scale uses the black-level correction. Both of those are their own
sections — here I'm just decoding the byte. But note the bit positions because it is
easy to off-by-one the shift and quietly swap which slot is "normalized."

#### The wb triple and the /10000 fixed-point (mistake #2)

`wb[0]`, `wb[1]`, `wb[2]` at bytes 6–7, 8–9, 10–11 are each a **uint16** stored as a
**fixed-point** value. The firmware took the floating-point white-balance multiplier,
multiplied by 10000, and rounded to the nearest integer. To recover the float you divide
back by 10000.

```
wb_float[i] = wb_uint16[i] / 10000.0
```

This is mistake #2 (after endianness) for a reason: people read the uint16, see a number
like `12030`, and either use `12030` directly (catastrophic) or divide by some other
power of ten because they eyeballed it. It is always 10000. A stored `12030` means a
white-balance multiplier of **1.2030**. A stored `9875` means **0.9875**. A stored
`10000` means exactly **1.0** (a unity / no-op channel gain, which is common).

Sanity range: in practice these multipliers live roughly in the 0.7–1.6 region, so the
recovered float should land in a believable neighborhood. If you "recover" 12030.0 you
forgot to divide; if you recover 1203.0 you divided by 10 instead of 10000.

#### The co triple — skip it, do not look at it

Bytes 15, 16, 17 are `co[0..2]`, the **debug channel-order** triple. This is the single
biggest trap in the layout, because it *looks* exactly like the kind of thing you'd want:
a three-byte permutation that seems to tell you how channels are ordered. It is a debug
artifact. It is sometimes self-consistent, sometimes plain wrong, sometimes a stale value
from a bench rig. **The channel mapping is decided by the sensor variant (bits 0–1 of the
flags) ALONE.** Never use `co` to route channels. Read past those three bytes and forget
they existed. They exist in the layout only so that the dev/site strings land at the right
offset; their *values* are noise to us.

I'm putting this here in the format section and not just in the channel-mapping section
on purpose, because the temptation strikes the moment you're staring at the bytes. You'll
see `co = [2,1,0]` next to a Variant B block and think "aha, slot order, confirmed." No.
Coincidence at best. Variant decides. Skip `co`.

#### dev and site: length-prefixed ASCII

After the 18-byte header you hit `dev_len`, a single uint8 saying how many ASCII bytes of
device id follow. Read that many bytes; that's `dev`. Immediately after the device id is
`site_len`, another uint8, then that many ASCII bytes of site id; that's `site`. Both are
plain ASCII — device ids look like `RBX-7A2C`, sites look like `site-lagoon`.

These two lengths are why you cannot hardcode offsets past byte 17. The CRC trailer's
position depends on `dev_len` and `site_len`. Parse the lengths, advance by them, and the
last two bytes after the site string are the CRC. Don't assume the blob is some fixed
total size; I've seen scripts hardcode "CRC is at byte 28" because that happened to be
true for one device's id length, then break on the next device.

The decoded `site` is also what we later look up in the site registry / model cards, and
what we cross-check against `global.yaml`'s `allowed_sites`. But that's downstream — here,
`site` is just the second length-prefixed ASCII string.

#### The CRC trailer (pointer only)

The final two bytes are a big-endian uint16 CRC-16 computed over *every preceding byte* of
the blob — magic, version, flags, seq, wb, blk, co, the length bytes, the dev/site strings,
all of it, right up to (but not including) the two CRC bytes themselves. The exact CRC
algorithm — which variant, which polynomial, the init value, how to verify your
implementation against a known check value — is **section 5**. I'm not repeating it here so
the two don't drift. For *this* section, all you need to know is: the last two bytes are a
big-endian CRC-16, and if it doesn't match what you recompute, the block is corrupt/truncated
and you quarantine it as `bad_checksum` (quarantine section has the full ladder). Parsing
stops mattering the instant the CRC fails — don't trust any field out of a block whose CRC
didn't check.

### A worked example — walking a fictional blob byte by byte

Let's make this concrete. Suppose a capture `rbx-7a2c-0005.png` carries a
`reefbox:calibration` `tEXt` value that base64-decodes to the following bytes. (Fictional
blob, hand-built for this walkthrough. The CRC bytes here are illustrative — verify real
ones per section 5.)

```
offset:  00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F 10 11 12
bytes :  52 42 02 14 00 05 2E F0 27 10 26 AC 02 00 03 02 01 00 08
         |__| |  |  |___| |___| |___| |___| |  |  |  |  |  |  |  |
         RB   v  fl seq   wb0   wb1   wb2  b0 b1 b2 c0 c1 c2 dl

offset:  13 14 15 16 17 18 19 1A    1B 1C 1D 1E 1F 20 21 22 23 24    25 26
bytes :  52 42 58 2D 37 41 32 43    0B 73 69 74 65 2D 6C 61 67 6F    6F 6E ...
         |________ dev (8) ________| |  |________ site (11) _____________|
                                     sl
```

Let me walk it:

- **00–01: `52 42`** → ASCII `"RB"`. Magic checks out. (Wrong magic here would mean a
  non-ReefBox or corrupt block → `bad_checksum`, but ours is fine.)
- **02: `02`** → version 2. So this is a 2.x block. Good — consistent with it living under
  `reefbox:calibration`.
- **03: `14`** → flags. `0x14` = binary `0001 0100`.
  - Bits 0–1: `0b00` = `0` → Variant **A**.
  - Bit 2 (`nz[0]`): `(0x14 >> 2) & 1` = `1` → slot 0 normalized.
  - Bit 3 (`nz[1]`): `(0x14 >> 3) & 1` = `0` → slot 1 raw.
  - Bit 4 (`nz[2]`): `(0x14 >> 4) & 1` = `1` → slot 2 normalized.
  - So: Variant A, nz = [1, 0, 1].
- **04–05: `00 05`** → seq. Big-endian: `0x0005` = **5**. (Matches the filename's `-0005`,
  which is reassuring but the seq comes from the bytes, not the filename — never trust the
  filename for seq.)
- **06–07: `2E F0`** → wb[0]. Big-endian uint16 = `0x2EF0` = 12016. Divide by 10000 →
  **1.2016**.
- **08–09: `27 10`** → wb[1]. `0x2710` = 10000. /10000 → **1.0000** (unity).
- **0A–0B: `26 AC`** → wb[2]. `0x26AC` = 9900. /10000 → **0.9900**.
- **0C: `02`** → blk[0] = 2.
- **0D: `00`** → blk[1] = 0.
- **0E: `03`** → blk[2] = 3. (All in 0..15. Good.)
- **0F–11: `02 01 00`** → co = [2, 1, 0]. This is the debug triple. **Ignore it.** See how
  it *looks* like a slot permutation? Resist. Variant A already told us the mapping is
  straight-through; `co` is noise.
- **12: `08`** → dev_len = 8. So the next 8 bytes are the device id.
- **13–1A: `52 42 58 2D 37 41 32 43`** → ASCII `R B X - 7 A 2 C` → **`RBX-7A2C`**.
- **1B: `0B`** → site_len = `0x0B` = 11. Next 11 bytes are the site id.
- **1C–26: `73 69 74 65 2D 6C 61 67 6F 6F 6E`** → ASCII `s i t e - l a g o o n` →
  **`site-lagoon`**.
- **(after site): the final two bytes** → big-endian CRC-16. You recompute the CRC over
  bytes 00 through the last `n` of the site string and compare to these two. Match → block
  is good and we proceed. (Algorithm: section 5.)

Decoded result for this capture:

```
version = 2
variant = A
nz      = [1, 0, 1]
seq     = 5
wb      = [1.2016, 1.0000, 0.9900]
blk     = [2, 0, 3]
co      = [2, 1, 0]   (ignored)
dev     = "RBX-7A2C"
site    = "site-lagoon"
```

Notice what we did NOT do: we didn't touch `co`, we didn't divide by anything but 10000,
and we read every multi-byte field big-endian. Three little disciplines, and the block
falls apart cleanly.

#### The same blob, read WRONG (so you recognize the smell)

It's worth seeing the failure modes, because they don't crash — they produce plausible
garbage.

- **Little-endian seq:** reading `00 05` as little-endian gives `0x0500` = 1280 instead of
  5. Now your dedup logic thinks this capture is *way* newer than its siblings and it wins
  every tiebreak it shouldn't. Insidious.
- **Little-endian wb[0]:** `2E F0` little-endian is `0xF02E` = 61486, /10000 = 6.1486. A
  white-balance gain of 6.1? Should scream "wrong endianness" — but if you're not sanity-
  checking ranges, it just silently blows out the red channel.
- **Forgot /10000:** wb[0] = 12016.0. Pixels go to the moon.
- **Divided by 1000:** wb[0] = 1.2016 *0.1* off… er, 12.016. Off by 10×. Just as wrong,
  harder to spot because it's "only" 10×.
- **Used `co` for mapping:** here `co=[2,1,0]` would have you route channels as if slots
  were reversed, on a Variant A block that's actually straight-through. You'd swap red and
  NIR for no reason. Variant decides; `co` is a decoy.

If your decoded numbers ever look physically absurd (gains of 6, 12000, 60000; seq values
in the thousands when you expected single digits), suspect endianness or the fixed-point
divide before you suspect the camera.

### A minimal parse recipe (pseudocode)

For the people who think in code, here's the shape of it. (Big-endian reads written
explicitly; this is intentionally not language-specific.)

```
b = base64_decode(text_value)

assert b[0:2] == "RB"          # else -> bad_checksum (see quarantine)
version = b[2]                 # 1 or 2; layout identical either way
flags   = b[3]
variant = flags & 0x03                 # 0=A, 1=B, 2=C
nz      = [ (flags>>2)&1, (flags>>3)&1, (flags>>4)&1 ]
seq     = (b[4]  << 8) | b[5]                       # BIG-ENDIAN uint16
wb      = [ ((b[6] <<8)|b[7])  / 10000.0,
            ((b[8] <<8)|b[9])  / 10000.0,
            ((b[10]<<8)|b[11]) / 10000.0 ]           # /10000 fixed-point
blk     = [ b[12], b[13], b[14] ]
# b[15], b[16], b[17] = co[0..2]  -> SKIP, never read for logic
dev_len = b[18]
dev     = ascii(b[19 : 19+dev_len])
i       = 19 + dev_len
site_len= b[i]
site    = ascii(b[i+1 : i+1+site_len])
j       = i + 1 + site_len
crc     = (b[j] << 8) | b[j+1]                        # BIG-ENDIAN uint16
# verify crc over b[0:j]  (algorithm: section 5)
```

The two `<<8 | ` reads and the `/10000.0` are the load-bearing lines. The `co` skip is the
load-bearing *omission*. Everything else is bookkeeping.

### A second worked example — a Variant B, 1.x, double-write capture

The first walkthrough was the easy case (Variant A, clean 2.x). Let's do a gnarlier one,
because the gnarly cases are where the rules earn their keep. Fictional capture
`rbx-22e9-0011.png`. This file is from the double-write batch, so it has BOTH a
`reefbox:calibration` chunk and an `rbx:cal` chunk. First rule fires immediately: 2.x key
present → we read `reefbox:calibration`, we ignore `rbx:cal`. Don't even decode the legacy
one. (For the record, the stale `rbx:cal` on this unit decodes to seq 9 with slightly
different wb — exactly the kind of months-old snapshot that would silently poison your
numbers if you grabbed it. We don't.)

The 2.x value base64-decodes to:

```
offset:  00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F 10 11 12
bytes :  52 42 02 05 00 0B 2A F8 27 10 31 2D 04 01 02 00 01 02 08
         RB   v  fl seq   wb0   wb1   wb2  b0 b1 b2 c0 c1 c2 dl
```

Walking the header:

- **00–01 `52 42`** → `"RB"`. Magic good.
- **02 `02`** → version 2. (Consistent with reading the 2.x key. Aside: even if this byte
  said `01`, we'd parse it identically — the version byte does not change the layout. It's
  informational. The thing that decides which *key* we read is which chunk exists, not this
  byte.)
- **03 `05`** → flags `0x05` = `0000 0101`.
  - Bits 0–1 = `0b01` = `1` → Variant **B**.
  - Bit 2 `nz[0]` = `(0x05>>2)&1` = `1` → slot 0 normalized.
  - Bit 3 `nz[1]` = `0` → slot 1 raw.
  - Bit 4 `nz[2]` = `0` → slot 2 raw.
  - Variant B, nz = [1, 0, 0].
- **04–05 `00 0B`** → seq = `0x000B` = **11**.
- **06–07 `2A F8`** → wb[0] = `0x2AF8` = 11000 → **1.1000**.
- **08–09 `27 10`** → wb[1] = 10000 → **1.0000**.
- **0A–0B `31 2D`** → wb[2] = `0x312D` = 12589 → **1.2589**.
- **0C–0E `04 01 02`** → blk = [4, 1, 2].
- **0F–11 `00 01 02`** → co = [0, 1, 2]. Looks like "identity order." **Skip it anyway.**
  This is the most seductive co value of all because it looks like "no permutation,
  nothing to see." It is still a debug artifact and still irrelevant. Variant B does the
  routing.
- **12 `08`** → dev_len = 8.

Then `RBX-22E9` (8 bytes), a site_len, the site string, and the CRC trailer — same shape as
before, so I won't re-spell the ASCII. Decoded header summary:

```
version = 2 ; variant = B ; nz = [1,0,0] ; seq = 11
wb = [1.1000, 1.0000, 1.2589] ; blk = [4,1,2] ; co = [0,1,2] (ignored)
dev = "RBX-22E9"
```

I'm deliberately *not* computing channel scales here — that's the per-channel-scale
section's job, and Variant B's slot-to-channel mapping is its own well-documented trap (the
re-benched truth: RED comes from slot 2, GREEN from slot 1, NIR from slot 0; an earlier note
had the two visible channels transposed and was superseded). The point of *this* example is
purely the decode: even on a double-write, Variant-B, legacy-adjacent capture, the byte
parse is mechanical once you (a) picked the 2.x key, (b) read big-endian, (c) divided wb by
10000, and (d) skipped co. Same four disciplines. Always the same four.

### INC-0418: the little-endian week (war story)

Worth recording because it cost us three days. Early in the 2.x rollout, a new batch of
captures from `site-pinnacle` started producing manifests where the red channel was blown
out on roughly half the devices and fine on the other half. Not all — *half*. That "half"
is the tell, in hindsight.

What had happened: someone had rewritten the seq read in a hurry and used the host's native
byte order (the analysis box is little-endian) instead of forcing big-endian. For seq values
that were palindromic-ish in their two bytes it didn't matter much, but for the rest the
"newest" capture per device got chosen wrong in dedup, so we were calibrating off the wrong
sibling capture entirely — sometimes one with a wildly different wb. The blown-out red wasn't
a wb bug per se; it was a *dedup* bug caused by a *byte-order* bug three steps upstream.

The fix was one line — force big-endian on the seq read (and we audited every other
multi-byte read while we were in there). The lesson we wrote on the whiteboard and never
erased: **there is no such thing as "host byte order" in this blob. It is big-endian,
everywhere, always.** If you're on a little-endian machine (you are) and you read a
multi-byte field without explicitly byte-swapping or using a big-endian reader, you have a
bug; you just might not have triggered the data that exposes it yet. INC-0418 is why we now
have the range sanity-check (gains in ~0.7–1.6, seq in plausible ranges) baked into the
parser as a warning — not to *fix* bad reads, but to scream when one happens.

### FAQ (things people ask in the channel every couple of months)

**Q: The `tEXt` value looks like gibberish. Is the PNG corrupt?**
A: Almost certainly not. It's base64 of binary; it's *supposed* to look like gibberish.
Decode the base64 first, then look at the bytes. Don't try to read the value with your eyes.

**Q: There are two text chunks with calibration-looking keys. Which one?**
A: If one of them is `reefbox:calibration`, that one — period. The other (`rbx:cal`) is the
stale legacy leftover from the double-write batch; ignore it. Only if there is *no*
`reefbox:calibration` do you read `rbx:cal`. Neither → `missing_calibration`.

**Q: The 2.x block failed to decode / its CRC is bad. Can I fall back to the `rbx:cal`
block that's right there?**
A: No. Once `reefbox:calibration` is chosen, a failure means `bad_checksum`, not "try the
other key." We tried fallback-on-failure in the 2.x era and it masked real corruption by
quietly substituting stale calibration. Don't reintroduce it.

**Q: What's `co` for? It looks like channel order.**
A: It's a debug channel-order triple. It is NOT used for routing. The sensor variant (flags
bits 0–1) decides channel mapping, alone. Skip bytes 15–17. The fact that `co` sometimes
looks "right" is a coincidence, not a signal.

**Q: I read wb as 11000. Is that the multiplier?**
A: No — divide by 10000. 11000 → 1.1000. The wb fields are uint16 fixed-point at a scale of
10000. Always 10000.

**Q: blk came out as 31. Is that valid?**
A: blk is a uint8 documented to live in 0..15. A value above 15 is suspicious — but note
blk doesn't have its own integrity check beyond the whole-block CRC. If the CRC passes, the
bytes are what the firmware wrote; if blk looks out of range *and* CRC passes, raise it in
the channel — don't silently clamp. (Handling of weird-but-valid values is an errata topic,
not a decode topic.)

**Q: Do I trust the `version` byte to tell me 1.x vs 2.x?**
A: The version byte is informational and matches the firmware era, but it does NOT decide
which key you read and it does NOT change the layout. Which *key* exists in the PNG is what
matters. Parse the bytes the same way regardless of whether byte 2 is 1 or 2.

**Q: Where's the CRC and how do I check it?**
A: Last two bytes, big-endian, over every preceding byte. Algorithm, init value, and the
known-answer check are in section 5. Don't roll your own from memory.

### Onboarding checklist for "I'm about to write a decoder"

Pin this above your desk. In order:

1. Find the `tEXt` chunks. If `reefbox:calibration` exists, that's your value. Else if
   `rbx:cal` exists, that's your value. Else `missing_calibration`.
2. Base64-decode the value to raw bytes. (Read the value verbatim; no re-wrapping.)
3. Check bytes 0–1 are `"RB"`. (Bad magic → bad_checksum.)
4. Read byte 2 (version, informational) and byte 3 (flags). Unpack variant = `flags & 3`;
   nz from bits 2/3/4.
5. Read seq (4–5) **big-endian**.
6. Read wb[0..2] (6–11) **big-endian**, **divide each by 10000**.
7. Read blk[0..2] (12–14) as plain bytes.
8. **Skip** co[0..2] (15–17). Do not read them into any decision.
9. Read dev_len (18), then dev (ASCII). Read site_len, then site (ASCII). Advance exactly.
10. Read the last two bytes as a **big-endian** CRC-16 and verify per section 5. Fail →
    bad_checksum, and do NOT fall back to the other key.

If every step is honest, the block is decoded and the rest of the pipeline can trust it.
The two steps people botch are 5/6 (big-endian, /10000) and 8 (skipping co). Everything
else is just walking offsets carefully because the dev/site strings are variable length.

### Recap / what to actually remember

If you skim back later, here's the irreducible core of this section:

1. **Read the right key.** `reefbox:calibration` (2.x) is authoritative; `rbx:cal` (1.x)
   is fallback only. **Both present → 2.x wins, ignore the stale `rbx:cal`** (double-write
   batch). Neither present → `missing_calibration`. Same byte layout for both keys.
2. **The value is base64 of a packed binary blob.** Decode, then parse bytes.
3. **EVERYTHING multi-byte is BIG-ENDIAN.** Mistake #1.
4. **`wb[i]` is uint16 fixed-point; divide by 10000** to get the float. Mistake #2. Always
   10000, never 1000, never "as-is."
5. **Layout:** `RB` magic / version / flags(variant lo-2-bits, nz bits 2-3-4) / seq u16 /
   wb[0..2] u16 / blk[0..2] u8 / co[0..2] u8 (**skip**) / dev_len + dev / site_len + site /
   crc16.
6. **`co` is a debug decoy. Never route channels with it. Variant alone decides mapping.**
7. **The trailer is a big-endian CRC-16 over all prior bytes.** Algorithm and corrupt-block
   handling are sections 5 / firmware-errata / quarantine, not here. If it fails, the
   capture is `bad_checksum` — and you do NOT fall back to the other key.

Decode it right and the rest of the pipeline is honest arithmetic. Decode it wrong and
you'll ship a manifest that looks perfect and lies. Big-endian, divide by 10000, skip
`co`. Go.
## Decoding the fields: flags bits, fixed-point, CRC, and the scale formula

OK. So by now you've (hopefully) base64-decoded the chunk value and you're staring at a little pile of bytes. Section 4 walked you through *where* each field lives in the blob — the offsets, the magic, the lengths. This section is about turning those raw bytes into numbers you can actually feed the pipeline. This is the part where people get tripped up, every single onboarding cycle, so I'm going to be annoyingly explicit. If you already know all this, skim to the worked example at the end and check your code against it.

Quick reminder of the ground rules that bite people here:

- **Everything multi-byte is big-endian.** Every uint16 in this blob. wb, seq, the crc trailer. Big-endian. If you read a uint16 little-endian you will get garbage that *sometimes looks plausible*, which is the worst kind of bug. (More on that landmine in the wb part.)
- The **co triple** (bytes 15/16/17) is a debug artifact. We do not decode it, we do not use it, we skip it. I mention it here only because newcomers see "channel-order triple" and assume it's how you map channels. It is not. Channel mapping comes from the variant bits in the flags byte (next subsection) and *only* from there. Section 6 beats this drum harder; I'm just nailing it down so you don't reach for `co` while you're elbow-deep in the flags byte.

Right. Let's decode.

---

### 5.1 The flags byte (byte 3): one byte, four facts

Byte 3 is a bit-field. One single byte carries the sensor variant *and* the three normalization flags. It is dense and it is easy to fat-finger. Here's the layout, bit by bit, LSB on the right:

```
 bit:   7   6   5   4   3   2   1   0
       [ - | - | - | nz2 nz1 nz0 |  variant ]
                      |   |   |     |_____|
                      |   |   |        \--- bits 0-1: sensor variant (2 bits)
                      |   |   \------------ bit 2: nz[0]
                      |   \---------------- bit 3: nz[1]
                      \-------------------- bit 4: nz[2]
       bits 5,6,7 are unused right now. Don't assume they're zero, just mask them off.
```

So four extractions, all from one byte:

```
variant = flags & 0x03            # low two bits: 0=A, 1=B, 2=C (3 is reserved/undefined)
nz[0]   = (flags >> 2) & 1        # bit 2
nz[1]   = (flags >> 3) & 1        # bit 3
nz[2]   = (flags >> 4) & 1        # bit 4
```

That's it. Memorize "variant low two, then nz climbs up bits 2-3-4." The reason `variant` gets a full two-bit field even though we only use values 0/1/2 is historical — somebody planned for four variants and we only ever shipped three (and C is a brick; see 5.5). Value `3` in those two bits should never appear in real captures; if you somehow see it, treat it as a malformed block, not as a fourth secret variant.

A word on *why* it's packed like this, since the question comes up. The firmware folks were squeezing the calibration block to fit a fixed tEXt budget on the 1.x boards, and a flags byte that holds both the variant selector and the three normalization flags saved them four bytes per capture versus storing each as its own byte. That mattered on the old hardware. It does not matter to us now — the 2.x blocks have headroom — but the layout was kept identical between versions on purpose (version 1 and version 2 have the *same byte layout*; only the version byte differs), so we still unpack the same bit-field either way. Don't write two different flags-decoders for v1 and v2. One decoder, same bit math, regardless of the version byte. The only thing the version byte changes is *which key wins* when both are present (that's the precedence stuff from Section 3, not a decoding difference).

One more habit worth building: when you log a decoded capture for debugging, log the flags byte in hex *and* the decoded variant/nz alongside it, like `flags=0x16 -> variant=C nz=[1,0,1]`. When something looks wrong two weeks later, the raw hex next to the interpretation is the fastest way to tell "the byte was weird" from "my decoder is weird." Costs nothing, saves hours.

#### Worked bit math on a fictional flags byte

Let's take a made-up flags byte and grind it out by hand, because seeing the binary makes it stick. Say the flags byte is `0x16`.

```
0x16 = 0001 0110  (binary)
```

Read it against the layout:

```
 bit:   7   6   5   4   3   2   1   0
        0   0   0   1   0   1   1   0
                    ^   ^   ^   ^---^
                   nz2 nz1 nz0  variant
```

Now pull each field:

- **variant** = `flags & 0x03`. `0x16 & 0x03` = `0001 0110 & 0000 0011` = `0000 0010` = `2`. Variant **C**. (Heads up — variant C means the capture is unusable, quarantine `sensor_variant_c`. We'll come back to that. For the *bit math* it doesn't matter; C decodes the same as anyone else, we just throw it away after.)
- **nz[0]** = `(flags >> 2) & 1`. Shift `0001 0110` right by 2 -> `0000 0101`, AND with 1 -> `1`. So nz[0] = **1** (normalized).
- **nz[1]** = `(flags >> 3) & 1`. Shift right by 3 -> `0000 0010`, AND with 1 -> `0`. So nz[1] = **0** (raw).
- **nz[2]** = `(flags >> 4) & 1`. Shift right by 4 -> `0000 0001`, AND with 1 -> `1`. So nz[2] = **1** (normalized).

So `0x16` decodes to: variant C, nz = `[1, 0, 1]`.

Let's do one more, a friendlier one, because most real captures are variant A or B. Say flags = `0x05`.

```
0x05 = 0000 0101

variant = 0x05 & 0x03 = 0000 0101 & 0000 0011 = 0000 0001 = 1   -> Variant B
nz[0]   = (0x05 >> 2) & 1 = (0000 0001) & 1 = 1                  -> nz[0]=1
nz[1]   = (0x05 >> 3) & 1 = (0000 0000) & 1 = 0                  -> nz[1]=0
nz[2]   = (0x05 >> 4) & 1 = (0000 0000) & 1 = 0                  -> nz[2]=0
```

`0x05` -> variant B, nz = `[1, 0, 0]`. We'll use this exact byte in the big worked example at the bottom, so keep it in mind.

One thing I want to hammer: **nz is indexed by stored slot, not by canonical channel.** `nz[0]` tells you whether *slot 0* was normalized, full stop. It says nothing yet about RED or GREEN or NIR. The same is true for wb and blk. The slot-to-channel mapping is a separate step that depends on the variant, and we don't do it until the scale formula. I'll keep repeating this because it is THE mistake. Decode `nz`, `wb`, `blk` as three slot-indexed arrays first. Map to channels later. Don't try to be clever and do it in one pass — you'll cross the wires on variant B and not notice until the colors come out wrong in inference, which is a miserable bug to chase from the manifest side.

---

### 5.2 wb: uint16 big-endian, fixed-point /10000

The white-balance values live at bytes 6-7 (wb[0]), 8-9 (wb[1]), 10-11 (wb[2]). Each is a uint16 stored big-endian, and it's a *fixed-point* value: the stored integer is `round(wb_float * 10000)`. To recover the float you divide by 10000.

So the read is two steps per slot:

```
raw = (byte_hi << 8) | byte_lo          # big-endian uint16
wb  = raw / 10000.0                      # recover the float
```

Example. Suppose bytes 6 and 7 are `0x3F` and `0x2A`.

```
raw = (0x3F << 8) | 0x2A = 0x3F2A = 16170
wb[0] = 16170 / 10000 = 1.6170
```

Another: bytes 8,9 = `0x27`, `0x10`.

```
raw = 0x2710 = 10000
wb[1] = 10000 / 10000 = 1.0000
```

(`0x2710` = exactly 10000 = wb of 1.0. You'll see this one a lot; a slot with no white-balance correction stores 1.0000 -> 10000 -> `0x27 0x10`. Handy sanity check.)

And bytes 10,11 = `0x1F`, `0x40`:

```
raw = 0x1F40 = 8000
wb[2] = 8000 / 10000 = 0.8000
```

So that fictional triple gives wb = `[1.6170, 1.0000, 0.8000]`.

**The big-endian landmine.** I promised I'd come back to it. If you accidentally read `0x2710` *little*-endian you get `0x1027` = 4144, which divided by 10000 is `0.4144`. That is a perfectly believable white-balance number! It won't blow up, it won't throw, it'll just be silently, subtly wrong, and you'll only find out when someone notices the NIR channel looks off in production three weeks later. Big-endian. Test against `0x2710 == 1.0`. If your decoder says `0x27 0x10` is anything other than 1.0000, stop and fix your byte order before going further.

Also: wb is a uint16, max stored value 65535, so the max representable wb float is `6.5535`. We've never seen a legitimate wb above ~2.5 in the field, so if you decode a wb of 5.x or 6.x, that's a smell — probably byte-order or you've mis-located the field. (It's not *illegal*, just unusual. Don't reject on it. Just raise an eyebrow.)

Why fixed-point at all, instead of storing a float? Two reasons, both about the old firmware. First, the 1.x boards had no floating-point unit worth the name, so integer math was cheaper and more predictable. Second, a `round(wb * 10000)` integer is *exact* — there's no float representation wobble, no "is it 1.6170 or 1.61699999" nonsense, the stored value is a clean integer and you divide once on read. The `* 10000` gives four decimal places of precision, which is plenty for white-balance; nobody's calibrating to the fifth decimal. When you recover the float, that division by 10000 is the *only* place float enters for wb, so it's also the only place rounding can sneak in — which is part of why we round the *final* scale at the end rather than rounding wb on the way in. Keep wb at full precision (1.6170, not pre-rounded) until the scale formula's done; see 5.5.

And don't be tempted to "clean up" a wb that comes out as something like 0.9999 or 1.0001 by snapping it to 1.0. Those are real calibration values, the camera measured them, leave them. The fixed-point encoding already gave you exactly what the firmware intended; second-guessing it just introduces error.

---

### 5.3 blk: plain uint8, range 0..15

The black-level values are dead simple compared to wb. Bytes 12, 13, 14 = blk[0], blk[1], blk[2], each a single uint8. No endianness (it's one byte), no scaling, no fixed-point. The byte value IS the number.

```
blk[0] = byte12
blk[1] = byte13
blk[2] = byte14
```

The documented range is 0..15. The firmware only ever writes the low nibble for these, so in practice you'll see values `0x00` through `0x0F`. If you decode a blk of, say, 40, something's wrong upstream — you've probably drifted by a byte somewhere (mis-read the dev_len/site_len lengths is the usual cause; see Section 4) and you're reading an ASCII character as a blk. The 0..15 ceiling is a useful tripwire for exactly that drift, but again — it's a smell, not a hard reject. Don't quarantine a capture just because blk looks big; go back and check your offsets first.

Like nz and wb: **blk is indexed by stored slot.** `blk[0]` is the black level of slot 0. We have not assigned it to a channel yet.

Worked: bytes 12,13,14 = `0x05`, `0x00`, `0x0A`.

```
blk[0] = 5
blk[1] = 0
blk[2] = 10
```

blk = `[5, 0, 10]`. Done. blk is the easy one.

---

### 5.4 The CRC: CRC-16/CCITT-FALSE, and how to actually check it

This is the integrity gate. The last two bytes of the block are a uint16 (big-endian, like everything else) CRC computed over **every preceding byte** — magic, version, flags, seq, wb, blk, co, dev_len, dev id, site_len, site id — all of it, up to but **not including** the two trailer bytes themselves. You recompute the CRC over that span and compare to the stored trailer. Match -> the block is intact. Mismatch -> the block is corrupt or truncated, and the capture gets quarantined as `bad_checksum`.

The exact algorithm matters, because "CRC-16" names about a dozen mutually-incompatible variants and they all produce different numbers. Ours is **CRC-16/CCITT-FALSE**. The parameters:

- **Polynomial: 0x1021**
- **Init: 0xFFFF**
- **Process MSB-first** (the bytes are fed in and shifted high-bit-first)
- **No input reflection** (don't bit-reverse the input bytes)
- **No output reflection** (don't bit-reverse the result)
- **No final XOR** (final XOR value is 0x0000 — i.e. you don't XOR the result with anything)

The "CCITT-FALSE" name is a historical misnomer for this exact parameter set; it's the one with init 0xFFFF and no reflection. Whatever you call it, the parameters above are what defines it, and the check value below is how you *prove* you implemented it.

**The check value.** This is the single most important debugging tool in this whole section. CRC-16/CCITT-FALSE computed over the ASCII string `"123456789"` (the nine bytes `0x31 0x32 ... 0x39`) is **0x29B1**. Every conformant implementation of this exact CRC produces `0x29B1` for that input. Before you trust your CRC against a single real capture, feed it `"123456789"` and assert you get `0x29B1`. If you don't, your CRC is wrong — wrong polynomial, wrong init, accidental reflection, or you XORed the output — and there's no point checking captures until that test passes.

Here's a reference bit-banged implementation (pseudocode, but it's basically copy-paste into any language):

```
function crc16_ccitt_false(bytes):
    crc = 0xFFFF                      # init
    for b in bytes:
        crc = crc XOR (b << 8)        # bring the byte into the high byte (MSB-first)
        for i in range(8):            # 8 bits per byte
            if crc & 0x8000:          # test the top bit
                crc = (crc << 1) XOR 0x1021
            else:
                crc = crc << 1
            crc = crc & 0xFFFF        # keep it 16-bit
    return crc                        # no final XOR, no reflection
```

Walk through why this matches the parameter set:

- `crc = 0xFFFF` at the start — that's **init 0xFFFF**.
- `crc XOR (b << 8)` shoves the input byte into the *high* 8 bits before clocking, and we test `0x8000` (the top bit) each iteration — that's **MSB-first, no input reflection**.
- The poly `0x1021` is XORed in whenever the top bit was set — **polynomial 0x1021**.
- We `return crc` directly, no bit-reversal and no XOR at the end — **no output reflection, no final XOR**.

If you'd rather use a table-driven CRC for speed, fine, but build the table from these same parameters and *still* verify against the `0x29B1` check value. A table built for a reflected CRC will sail through your unit tests on synthetic data and then disagree with the firmware on real captures. The check value is the only thing that catches that.

#### Checking a block

Concretely, given the decoded blob `B` of length `N` bytes (including the 2-byte trailer):

```
payload = B[0 : N-2]                     # everything except the last two bytes
trailer = (B[N-2] << 8) | B[N-1]         # the stored CRC, big-endian uint16
computed = crc16_ccitt_false(payload)
if computed != trailer:
    quarantine this capture as bad_checksum
```

Note the trailer is read big-endian, same as wb and seq. `B[N-2]` is the high byte, `B[N-1]` is the low byte.

A subtle point worth stating: the CRC covers the `co` debug triple even though we *ignore* `co` when computing scales. "Ignore co" means "don't use its value to map channels." It does **not** mean "skip those bytes when CRC-ing." The CRC is over the raw byte stream, all of it. Skip co in the *semantic* decode, never in the CRC span.

A couple of failure modes the CRC actually catches in the field, so you know what you're protecting against:

- **Truncation.** A capture got cut short — partial write to the card, a yanked cable mid-flush, whatever — and the block is missing its tail. The dev/site lengths might still parse into *something*, but the bytes are short and the CRC won't reconcile. Quarantine `bad_checksum`. The CRC is the only thing standing between you and silently decoding a half-written blob into plausible-looking garbage.
- **Bit rot / corruption.** A single flipped bit anywhere in the payload — a flaky SD card, cosmic ray, bad cable — and the recomputed CRC diverges from the trailer. CRC-16 won't catch *every* multi-bit pattern (no 16-bit CRC can), but it catches all single-bit flips and the overwhelming majority of real-world corruption, which is exactly the regime we're in.
- **Offset drift in your own decoder.** If *your* parser mis-read a length byte and grabbed the wrong span, your "payload" and your "trailer" won't line up and the CRC will scream. That's a gift — it means the CRC is also a check on *your* parsing, not just on the data. A capture that decodes "cleanly" but fails CRC is at least as often a decoder bug as it is real corruption, so when CRC fails, double-check your offsets before you blame the camera.

Practical note on the trailer: people occasionally try to "include" the trailer in the CRC computation and expect the result to come out zero (some CRC schemes are designed so that CRC-ing the message *with* its own check value yields a known residue). Ours is not set up to be used that way in our pipeline, and chasing that property is a distraction. Do the simple, unambiguous thing: CRC the payload (everything but the last two bytes), compare to the trailer read as a big-endian uint16, done.

And reminder of where this sits in the pipeline: integrity is a gate, not the last step. If the chosen block's magic is wrong, or it won't parse, or this CRC fails, the capture is `bad_checksum` and we never get to computing scales for it. Conversely, a clean CRC does *not* mean the capture is usable — a variant-C capture can have a perfectly valid CRC and still get quarantined as `sensor_variant_c`. CRC says "the bytes are intact," nothing more. Don't conflate "passes CRC" with "good capture."

---

### 5.5 The per-channel scale formula

Now the payoff. We have, per stored slot `s` (s in {0,1,2}):

- `wb[s]` — the recovered white-balance float
- `blk[s]` — the black level (0..15)
- `nz[s]` — the normalization flag (0 or 1)

And we want one **scale** value for each canonical channel — RED, GREEN, NIR, always in that order.

**Step 1: map channels to slots using the variant.** This is the step everyone wants to skip and cannot. The canonical output order is always RED, GREEN, NIR, but *which stored slot feeds each channel* depends on the variant bits we pulled out of the flags byte in 5.1:

- **Variant A** (straight through): RED <- slot0, GREEN <- slot1, NIR <- slot2.
- **Variant B** (cost-down board): RED <- slot2, GREEN <- slot1, NIR <- slot0. The two visible channels are swapped relative to A. (If you've read an old note that said RED is slot1 / GREEN is slot2 for variant B — that note is superseded. The re-bench transposed the visible channels. The correct, current mapping is RED <- **slot2**, GREEN <- slot1, NIR <- slot0. Trust this, not the old cheat-sheet.)
- **Variant C**: unusable, quarantine `sensor_variant_c`. You never compute scales for a C capture, so the mapping question is moot.

So for each canonical channel you figure out its mapped slot `s`, and *then* you look up `wb[s]`, `blk[s]`, `nz[s]` for that slot. The white-balance, black-level, and normalization flag all travel together with the slot. You don't mix slot-2's wb with slot-1's blk or anything cursed like that — pick the slot, take all three of its values.

**Step 2: apply the scale formula, per channel, using that channel's mapped slot `s`:**

```
if nz[s] == 1:                           # slot was normalized
    scale = wb[s] * (255 - blk[s]) / 255
if nz[s] == 0:                           # slot was raw
    scale = wb[s]
```

In words: if the slot feeding this channel was **normalized** (nz==1), the scale is the white-balance times a black-level correction factor `(255 - blk[s]) / 255`. If the slot was **raw** (nz==0), the black level doesn't enter at all and the scale is just the white-balance straight up.

**Step 3: round to 6 decimal places — once, at the end.** Compute the full expression in floating point, *then* round the final scale to 6 dp. Don't round wb, then round the intermediate product, then round again — that compounds rounding error. One rounding, at the very end, on the final scale value. Do this independently for each of the three channels.

A couple of notes on the formula:

- The `(255 - blk[s]) / 255` factor is always `<= 1` (since blk is 0..15, the factor ranges from `(255-15)/255 = 0.941176...` up to `255/255 = 1.0`). It pulls the scale *down* slightly to account for the sensor's black floor. When `blk[s] == 0` the factor is exactly 1 and the normalized formula collapses to just `wb[s]` — same as the raw case. So a normalized slot with zero black level gives the same scale as a raw slot with the same wb. That's expected, not a bug.
- The 255 is a literal constant (8-bit full scale), not derived from anything in the blob. Don't go looking for a "255 field." It's just the math.

---

### 5.6 Full worked example (Variant B, with the corrected mapping)

Let's do one end to end with real fictional numbers, because the slot/channel indirection is exactly the thing that bites, and Variant B is where it bites hardest. I'll use a capture from a made-up device on a made-up site so nobody confuses it with a real unit.

Say we've decoded a block (CRC already verified — pretend it passed) with these field values:

```
flags  = 0x05
seq    = 0x000C  (12)
wb     = [1.6170, 1.0000, 0.8000]     (slots 0,1,2)
blk    = [5,      0,      10]          (slots 0,1,2)
```

First, decode the flags byte. We did this one back in 5.1: `0x05` ->

```
variant = 0x05 & 0x03 = 1            -> Variant B
nz[0]   = (0x05 >> 2) & 1 = 1
nz[1]   = (0x05 >> 3) & 1 = 0
nz[2]   = (0x05 >> 4) & 1 = 0
```

So: **Variant B**, nz = `[1, 0, 0]` (indexed by slot). slot0 normalized, slot1 raw, slot2 raw.

Now the slot-to-channel map for Variant B (the corrected one — RED<-slot2, GREEN<-slot1, NIR<-slot0):

```
RED   <- slot 2
GREEN <- slot 1
NIR   <- slot 0
```

Pull the per-slot values for each channel and apply the formula.

**RED — mapped slot 2.** For slot 2: wb[2] = 0.8000, blk[2] = 10, nz[2] = 0 (raw).

```
nz[2] == 0  -> scale = wb[2] = 0.8000
RED scale = 0.800000   (round to 6 dp)
```

The black level (10) does NOT enter, because slot 2 is raw. Easy to want to subtract it. Don't.

**GREEN — mapped slot 1.** For slot 1: wb[1] = 1.0000, blk[1] = 0, nz[1] = 0 (raw).

```
nz[1] == 0  -> scale = wb[1] = 1.0000
GREEN scale = 1.000000
```

**NIR — mapped slot 0.** For slot 0: wb[0] = 1.6170, blk[0] = 5, nz[0] = 1 (normalized!).

```
nz[0] == 1  -> scale = wb[0] * (255 - blk[0]) / 255
            = 1.6170 * (255 - 5) / 255
            = 1.6170 * 250 / 255
            = 1.6170 * 0.980392156862745...
            = 1.585294117647...
NIR scale = 1.585294   (round to 6 dp, once, at the end)
```

So the final channel_scales for this capture:

```
RED:   0.800000
GREEN: 1.000000
NIR:   1.585294
```

Now look at what just happened, because this is the whole point of all the slot/channel nagging: the **largest** white-balance value (1.6170, in slot 0) ended up driving the **NIR** channel, and the **smallest** (0.8000, in slot 2) drove **RED** — because on Variant B the visible channels are transposed and the data lands in the "wrong" slots relative to channel order. If you had naively assumed slot0=RED (the Variant A mapping, or the straight-through intuition), you'd have reported RED=1.585294 and NIR=0.800000 — exactly backwards, and with the black-level correction applied to the wrong channel on top of it. Nothing would error. The manifest would look totally reasonable. And the classifier would quietly underperform. THAT is why we map slots to channels by variant first, every time, and why I keep saying it.

For contrast, here's the same blob if it had been **Variant A** instead (flags would've been `0x04` to keep nz the same: variant 0, nz[0]=1). Then RED<-slot0, GREEN<-slot1, NIR<-slot2:

```
RED   <- slot0: nz=1 -> 1.6170 * (255-5)/255 = 1.585294
GREEN <- slot1: nz=0 -> 1.0000           = 1.000000
NIR   <- slot2: nz=0 -> 0.8000           = 0.800000
```

Same bytes, same numbers, completely different channel assignment. The only thing that changed was two bits in the flags byte. Respect the flags byte.

---

### 5.7 Decode checklist (tape this to your monitor)

1. Pull `flags = byte[3]`. Compute `variant = flags & 0x03`, `nz[0]=(flags>>2)&1`, `nz[1]=(flags>>3)&1`, `nz[2]=(flags>>4)&1`. If variant == 2, it's C -> `sensor_variant_c`, stop.
2. Read `wb[0..2]` as big-endian uint16 from bytes 6-11, divide each by 10000. Sanity: `0x2710` must come out 1.0.
3. Read `blk[0..2]` as plain uint8 from bytes 12-14. Sanity: each should be 0..15.
4. Skip `co` (bytes 15-17) semantically — but it's still inside the CRC span.
5. CRC: recompute CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, MSB-first, no reflection, no final XOR) over all bytes except the trailing two; compare to the big-endian trailer. Mismatch -> `bad_checksum`. (Self-test your CRC: `"123456789"` -> `0x29B1`.)
6. Map channels to slots by variant (A: RED0/GREEN1/NIR2; B: RED2/GREEN1/NIR0).
7. For each channel's mapped slot `s`: `nz[s]==1 -> wb[s]*(255-blk[s])/255`, else `wb[s]`. Round to 6 dp, once, at the end.

Get those seven steps right and the rest of the pipeline is just bookkeeping. Get the flags byte or the byte order wrong and everything downstream is confidently incorrect. Decode slowly, test against the check value and the worked numbers above, and don't trust a decoder you haven't proven with `0x29B1`.
## INC-2207: the classifier rejects every capture

**Filed:** by Priya, after the Lagoon-3 redeploy. Tagged: classifier, manifest, calibration, "lost a whole survey day to base64".

Writing this up while it's still fresh because I do not want anyone else to burn the hours we burned. Short version for the impatient: the offline classifier refused *every single capture* from the Lagoon-3 survey — 41 PNGs, zero accepted — and the reason was not the model, not the images, not the GPU box. The reason was that the deploy manifest we handed the classifier had **no per-device calibration in it**, because the calibration was never plain text sitting in a file like we all assumed. It was riding inside each PNG's own metadata, base64-encoded, as a packed binary blob. We'd been shipping it the whole time and never reading it.

If you only read one section before your first deploy, read this one.

### What we saw

The classifier runs offline on the survey laptop. You point it at a directory of `.png` captures plus a `manifest.json`, and it spits out per-image label sets. Standard. We've done it a hundred times on the older 1.x boxes.

Lagoon-3 was the first survey we did entirely on the new 2.x ReefBox firmware. We pulled the cards, copied 41 captures off (`rbx-7a2c-0001.png` through `rbx-7a2c-0041.png` and a handful from a second unit, `rbx-22e9-*`), built the manifest the way we always do, and ran inference.

Every image came back rejected. The classifier log was a wall of the same line:

```
[reject] rbx-7a2c-0005.png: no calibration for device; refusing to infer (channel_scales required)
[reject] rbx-7a2c-0006.png: no calibration for device; refusing to infer (channel_scales required)
[reject] rbx-7a2c-0007.png: no calibration for device; refusing to infer (channel_scales required)
...
```

41 of those. Then a one-line summary: `included=0 quarantined=41`. Not a crash. Not a stack trace. A clean, deliberate refusal. The classifier was doing exactly what it's supposed to do: it will not run a capture it can't calibrate, because an uncalibrated NIR channel will silently turn a healthy coral patch into a "bleaching event" and nobody wants to be the one who reported a fake bleaching event to the regional office. So far so good. The classifier was right to be stubborn. The bug was upstream of it, in *us*.

### First wrong guess: "the model card is broken"

Naturally the first thing I did was blame the YAML, because that's where settings live and that's the part humans hand-edit. I opened `global.yaml`, the `sites/site-lagoon.yaml` card, and the `devices/` directory.

Everything looked fine. `global.yaml` had the baseline `model_name`, `model_version`, `labels_version`, `input_size`, `confidence_threshold`, and the `allowed_sites` list (and yes, `site-lagoon` was in `allowed_sites`, I checked that three times after the *last* incident taught me to). The site card had its own `input_size` for the Lagoon mount geometry. There was a `devices/rbx-7a2c.yaml` with a model override.

So the model cards were healthy. The classifier wasn't complaining about model settings anyway — re-read the error. It said **"no calibration for device"** and **"channel_scales required"**. Those words are the tell. `channel_scales` is the per-channel RED/GREEN/NIR multiplier the classifier needs to white-balance and de-black-level each image before it runs. It is *not* something you put in a model card. It's per-camera, per-capture physics. The model cards have never carried it and never should.

I wasted maybe forty minutes here because I pattern-matched "manifest problem" to "YAML problem". They are not the same problem. The YAML is the *inference settings*. The calibration is the *optics*. Different worlds. Write that on your hand.

### Second wrong guess: "the calibration file didn't get copied"

OK so the classifier wants `channel_scales` per device and the manifest doesn't have them. Where do channel scales come from? On the old 1.x workflow there was a `calibration.txt` sidecar — a little human-readable file the bench team dropped next to the captures, lines like `RBX-old: wb 1.02 / 0.98 / 1.11 ...`. The build script slurped that and folded it into the manifest. Easy.

So I went looking for the sidecar. There wasn't one. There was no `calibration.txt`, no `cal.json`, no `*.cal`, nothing. I assumed the bench team forgot to export it and pinged them. Diego (bench) replied within five minutes, and his reply is the whole reason this incident has a happy ending:

> "There's no sidecar on 2.x. We stopped shipping `calibration.txt` like a year ago. The cal goes *into the image* now. It's in the PNG. Look in the text chunks."

Cue the sound of a penny dropping. Loudly.

### The actual root cause: the calibration is *in the PNG*

Here is the thing nobody on the survey side had internalized: starting with 2.x firmware, the ReefBox writes its calibration **into the PNG itself**, as a `tEXt` metadata chunk. There is no separate file. The image *is* the carrier. If you copy the PNG, you've copied the calibration; if you strip metadata (more on that horror later), you've thrown the calibration away.

I dumped the chunks on `rbx-7a2c-0005.png`. Any tool that lists PNG ancillary chunks works; I used a quick chunk lister. There it was:

```
IHDR  13 bytes
tEXt  "reefbox:calibration"  -> (long base64-looking string)
IDAT  ...
IEND
```

A `tEXt` chunk whose **keyword** was `reefbox:calibration`, and whose **value** was a long string of `[A-Za-z0-9+/]` ending in `=`. My first instinct — and I bet yours too — was "great, the value is text, I'll just parse the text." It is **not** text. It looks like text because base64 always looks like text. That's the trap. The value is **base64**, and when you decode the base64 you do **not** get a readable string — you get raw bytes. A packed binary blob.

Quick proof it's binary and not, say, base64-of-JSON. I decoded it and hexdumped the first bytes (fictional blob, but representative of the shape):

```
52 42 02 0c 00 05 27 8f 26 96 2b 9a 03 01 02 ...
 R  B  ^  ^  ^seq^ ^--- wb pairs ---  blk...
```

That `52 42` at the very front is ASCII `"RB"` — the magic. Then a version byte, a flags byte, a 2-byte sequence number, then a run of 16-bit values, then some single bytes, then what's clearly a length-prefixed ASCII run (`03 01 02` is not text but a few bytes later you can literally read the device id and the site id in ASCII). If you base64-*decode* this and try to read it as a UTF-8 string, you get mojibake and a shrug. It is a structured binary record. The base64 is just the envelope that lets binary survive inside a text-only PNG chunk.

So the real failure chain for INC-2207 was:

1. 2.x firmware stopped shipping a sidecar and started embedding calibration in each PNG's `tEXt` chunk, base64-encoded, as packed binary.
2. Our manifest build script was still the 1.x version: it looked for a `calibration.txt` sidecar, found none, and — this is the genuinely bad part — **silently** wrote a manifest with empty `channel_scales` instead of failing loudly. The build "succeeded".
3. The classifier got a manifest with no calibration for any device, correctly refused to infer, and rejected all 41 captures.

The manifest builder's silence is its own bug and I've filed it separately, but the *design* lesson is the one that matters: **on 2.x, the calibration is not a file you can forget to copy — it's data you have to decode.** The bytes were in our hands the entire time. We just never opened the envelope.

### Why this is annoying, and why it's actually good

It feels hostile the first time. "Why would you hide the calibration inside the image instead of just giving me a JSON file?" But once you live with it, the embed-in-PNG design is the right call for field work:

- **The calibration can never get separated from the capture.** No more "which `calibration.txt` goes with which card?" The cal is welded to the pixels it calibrates. Copy the image, you copied the truth.
- **It survives sneakernet.** We move data on SD cards through boats with no network. A sidecar gets dropped, renamed, or left behind. A `tEXt` chunk rides along inside the file.
- **It's per-capture.** Each PNG carries *its own* block, with its own sequence number. That matters later for de-duplication when a device writes the same `dev` across multiple captures.

The cost is exactly what bit us: you can't `cat` the calibration. You have to (a) read the right PNG metadata key, (b) base64-decode it, and (c) parse the binary. None of those three steps is hard, but if your toolchain skips any of them you get a confident, wrong, *empty* result.

### The fork in the road: which key wins

While poking at chunks I hit a second landmine that I'll flag now so the next person doesn't panic. On one of the second-unit captures (`rbx-22e9-0003.png`) I found **two** text chunks that both looked like calibration:

```
tEXt  "reefbox:calibration"  -> (base64...)
tEXt  "rbx:cal"              -> (different base64...)
```

Two keys. `reefbox:calibration` is the 2.x (modern) key and is **authoritative**. `rbx:cal` is the legacy 1.x key and is a **fallback only**. Diego confirmed this unit was from the infamous "double-write" bad batch — a run of 2.x units whose firmware wrote *both* keys, leaving a stale legacy `rbx:cal` block sitting next to the real one. The rule is simple and you must not get it backwards: **when both keys are present, the `reefbox:calibration` (2.x) block wins and the leftover `rbx:cal` block is ignored.** You only fall back to `rbx:cal` when `reefbox:calibration` is absent. And if *neither* key is present, that capture has no calibration at all and gets quarantined as `missing_calibration` — which, in hindsight, is the *correct* per-capture outcome our broken builder should have produced for the whole survey instead of writing empty scales.

(I have not yet decoded the binary byte-for-byte in this entry — that's its own deep-dive, see the later section on the block layout, the `RB` magic, big-endian fields, the white-balance fixed-point, the black-levels, the normalization flags, the variant in the flags byte, and the CRC trailer. Here I just needed to know *where the bytes live and which copy to trust*. Decoding them correctly is the next mission.)

### The new motivation: fold the decoded block into the manifest

This incident is what turned "we should probably understand that blob someday" into a P1. The classifier's contract is clear and not negotiable: it wants a manifest where each included device has real `channel_scales` (RED, GREEN, NIR) plus its model settings and site. We can't change the classifier — and we shouldn't, its refusal saved us from publishing garbage. So the fix has to happen in the manifest build:

**New pipeline (what the builder must do, per capture):**

1. Open the PNG and read its `tEXt` chunks.
2. Pick the calibration key: prefer `reefbox:calibration`; if it's missing, fall back to `rbx:cal`; if neither, quarantine `missing_calibration`.
3. **Base64-decode** the chosen value into raw bytes. (Do not treat the value as text. I will keep saying this until it's reflexive.)
4. Parse the packed binary block: confirm the `RB` magic, read the fields big-endian, recover white-balance from the fixed-point integers, read black-levels and the normalization flags, read the sensor variant out of the flags byte, read the length-prefixed device id and site id, and verify the CRC trailer. If the magic is wrong or it won't parse or the CRC doesn't match the trailer, quarantine `bad_checksum`.
5. From the variant + flags + white-balance + black-levels, compute the per-channel `channel_scales` for the canonical RED/GREEN/NIR order and round to 6 decimals.
6. Look up the decoded **site** against `global.yaml`'s `allowed_sites`; resolve model settings from the YAML precedence rules; emit the device into the manifest.

In other words: the calibration we were missing was never missing. It was sitting base64-encoded in every PNG, and the job is to *reverse-engineer that binary block and fold its output into the manifest the classifier already knows how to read.* That's the whole arc this notebook is building toward.

### Concrete repro and the quick smell test

For anyone trying to reproduce INC-2207 or sanity-check a new survey before you waste a whole inference run:

Smell test #1 — does the PNG even carry calibration? List the text chunks and look for the keyword:

```
$ pngchunks rbx-7a2c-0005.png | grep tEXt
tEXt  keyword="reefbox:calibration"  length=58
```

If you see `reefbox:calibration` (or, on older units, `rbx:cal`), the cal is in there. If you see neither, that capture is headed for `missing_calibration` and you should know that *before* you build, not after the classifier tells you.

Smell test #2 — is the value really base64-of-binary and not plain text? Decode it and look at the first two bytes. They must be ASCII `R` `B` (`0x52 0x42`):

```
$ pngchunk-get rbx-7a2c-0005.png reefbox:calibration | base64 -d | head -c 3 | xxd
00000000: 5242 02                                  RB.
```

`52 42` = `RB` = magic present, version byte right behind it. If instead you decode and get something that reads like JSON or a sentence, stop — you're looking at the wrong chunk or someone re-encoded the file. The genuine block is binary.

Smell test #3 — did our builder silently emit empty scales? Grep the produced manifest:

```
$ jq '.devices[] | select(.channel_scales == null or .channel_scales == {})' manifest.json
```

If that returns anything, your manifest is the INC-2207 manifest and the classifier is going to reject those devices. The fix is upstream, in the decode step, not in the YAML.

### What we changed immediately (stopgaps) and what's still open

Same-day stopgaps so we could get *some* of Lagoon-3 processed:

- Hand-decoded two representative blocks (one Variant A unit, one of the cost-down boards) so we could eyeball that the byte layout matched what Diego described, confirmed the `RB` magic and that the CRC trailer checked out, and manually pasted scales for those two devices into the manifest. Ugly, but it got the classifier to *accept* instead of reject, which proved the diagnosis: feed it real `channel_scales` and the rejections vanish.
- Filed a loud-failure bug against the manifest builder: it must **never** write empty `channel_scales` silently. If it can't decode a block, that capture is quarantined with a reason code, full stop. Silent empty output is how a one-line config drift became a lost survey day.

Still open, and these become their own sections:

- **Decode the binary block end to end.** Magic, version, flags, sequence, white-balance fixed-point, black-levels, normalization flags, the variant bits, the device/site strings, and the CRC-16 trailer. There's also a debug channel-order triple sitting in the block that, per the bench notes, we are supposed to **ignore** — Diego was very firm that the channel mapping comes from the *variant*, never from that debug triple, but I'll leave the gory details to the layout section.
- **The variant-to-channel mapping**, especially for the cost-down "Variant B" boards, which do not map straight through. (There's apparently a re-bench note that *corrected* an earlier mapping. Trust the errata, not the cheat-sheet — read the latest before you wire up RED/GREEN/NIR.)
- **De-duplication.** Two captures off the second unit carried the same device id; only the highest-sequence one should survive and the rest get quarantined. Our stopgap manifest accidentally kept both. Bug noted.
- **Quarantine plumbing.** The classifier was doing crude all-or-nothing rejection only because we fed it a broken manifest. The *correct* behavior is per-capture: each rejected capture gets exactly one reason code, evaluated in a fixed order, and lands in a `quarantined` list in the manifest instead of silently vanishing.

### The one-paragraph lesson

If a 2.x ReefBox survey gets rejected wholesale by the classifier with "no calibration / channel_scales required", do **not** go hunting for a `calibration.txt` sidecar — there isn't one anymore. The calibration lives **inside each PNG**, in a `tEXt` chunk keyed `reefbox:calibration` (or legacy `rbx:cal` as fallback), and its value is **base64 of a packed binary blob**, not plain text. You decode the base64, parse the bytes (they start with `RB`), compute the channel scales, and fold those into the manifest the classifier reads. We had the calibration the whole time. We just hadn't opened the envelope. Open the envelope.

*— Priya, end of a long day. Next entry: actually cracking the byte layout.*
## INC-2231: the "co" bytes and the channel-order trap

*Filed by Priya (offline-inference on-call) with append notes from Devon and Sam. Original incident date 2024-03-18; this section was rewritten 2024-05-02 after we finally understood what happened, so read it as the corrected version, not the panic-thread version. If you're here because the cheat-sheet told you to "use co for channel order" — stop, that advice is wrong, jump to the resolution and come back.*

### TL;DR for the person who's mid-firefight

If your reef classifier suddenly thinks every coral head is open sand and every fish is a rock, and you recently "fixed" channel ordering using the three bytes at offsets 15, 16, 17 of the decoded calibration blob — you fell into the `co` trap. Those three bytes are a **debug dump**. They are not the channel order. Throw them away. **Skip exactly three bytes** after the blk triple and move on to `dev_len`. Map RED/GREEN/NIR from the **sensor variant alone** (the low two bits of the flags byte). That's the whole fix. The rest of this section is the story of how we lost most of a week's inference to those three bytes, and why miscounting them is even worse than misreading them.

### What happened

Background: we run the classifier offline, in nightly batches. A capture comes off a ReefBox as a PNG, we pull the calibration block out of the tEXt chunk, base64-decode it, parse the packed binary, build per-channel scales, and hand a normalized 3-plane tensor (RED, GREEN, NIR, in that canonical order) to the model. Nothing about this is real-time, which is both a blessing and a curse: a blessing because nobody's reef survey is blocked while we sort it out, a curse because a bad decode can sit in production for days before anyone notices the accuracy is in the toilet.

On the night of 2024-03-17 → 03-18, the batch that came in from the lagoon deployment scored *catastrophically* low on our held-out spot-check set. Not "a few percent off." We keep a tiny rolling sanity set of ~40 hand-labeled crops per site that we score every night purely to catch exactly this kind of regression, and the top-1 on that set dropped from the high 0.8s to roughly 0.21. That's worse than chance-with-a-prior in a lot of cells. When a vision model goes from 0.88 to 0.21 overnight and the weights didn't change, it is almost never "the model got dumber." It's the input pipeline. Something upstream is feeding it garbage that's *structured* garbage — consistent enough that the net confidently produces nonsense.

Devon had merged a change two days earlier titled, and I quote the commit message, "honor stored channel order from calibration (co triple) instead of assuming variant mapping." On paper that sounds *more* correct, not less — why would you *assume* a mapping when the device wrote down the order for you? That instinct is the trap. We'll dissect it.

### The change that caused it

Here's the shape of what Devon did. Recall the decoded blob layout (abbreviated; full layout lives in the decoding section, this is just the neighborhood we care about):

```
byte  3        : flags  (bits 0-1 = sensor variant; bits 2/3/4 = nz[0],nz[1],nz[2])
bytes 4-5      : seq (uint16, big-endian)
bytes 6-7      : wb[0]   8-9: wb[1]   10-11: wb[2]   (uint16 fixed-point /10000)
bytes 12,13,14 : blk[0], blk[1], blk[2]   (uint8 each, 0..15)
bytes 15,16,17 : co[0], co[1], co[2]      (uint8 each)   <-- THE DEBUG TRIPLE
byte  18       : dev_len (uint8), then dev_len ASCII bytes = device id
next           : site_len (uint8), then site_len ASCII bytes = site id
last 2 bytes   : crc16 (big-endian) over every preceding byte
```

The old (correct) decoder did this, conceptually:

```
slot_for_blk = read 3 bytes at 12..14
skip 3 bytes at 15..17          # co: debug, never used
dev_len = byte at 18
...
# channel mapping decided ENTIRELY by variant:
#   A: RED<-slot0, GREEN<-slot1, NIR<-slot2
#   B: RED<-slot2, GREEN<-slot1, NIR<-slot0
#   C: unusable (sensor_variant_c)
```

Devon's change deleted the "skip 3 bytes" comment-and-skip and instead *read* `co[0..2]` as a permutation, then used it to pick which stored slot fed RED, GREEN, NIR. Something like:

```
co = read 3 bytes at 15..17
RED   = slot[ co[0] ]
GREEN = slot[ co[1] ]
NIR   = slot[ co[2] ]
```

It looked reasonable. It even ran clean. The CRC still passed (of course it did — he was still *reading past* those bytes to reach the same trailer; more on the subtle version of this failure below). The manifests built without errors. And for some captures it even produced the *right* answer by accident, because on a Variant A unit a `co` of `[0,1,2]` happens to agree with straight-through mapping. That partial agreement is exactly what let the bug hide for two days: the units where `co` was an identity-ish triple looked fine, and only the ones where `co` was something weird got scrambled.

### Why `co` is garbage (the part nobody documented until now)

I went and talked to the firmware folks, because none of us actually knew what `co` *was*, we'd just been dutifully skipping it because the decoding section said to. Here's the real story, finally written down.

`co` stands for "channel order," yes — but it's the channel order **of an internal debug readout path on the sensor's test rig**, not the order of the slots as they're stored in *this* blob. During factory bring-up the firmware has a diagnostic mode that dumps raw sensor lanes in whatever order the bring-up harness was wired that day, and `co` records the lane order *that harness saw*. It has nothing to do with how the production firmware lays out `wb`/`blk`/the stored slots in the calibration block you're decoding. On some board spins the bring-up harness was wired straight, so `co` came out `[0,1,2]`. On others — notably a chunk of the cost-down Variant B boards — the harness was wired to match the *debug* lane order, which is its own thing entirely, and `co` came out as `[2,1,0]` or `[1,2,0]` or other permutations that have **no fixed relationship** to the real stored-slot-to-channel mapping.

In other words: `co` is a souvenir from the test bench. Treating it as authoritative channel order is like reading the order the parts were unpacked from the shipping box and concluding that's how the engine is plumbed. Sometimes it lines up. Usually it doesn't. And critically, **the production firmware never reads `co` back** — it's write-only telemetry that got left in the packed format because removing a field from the blob layout is a bigger firmware change than just continuing to emit a dead triple. So it sits there at bytes 15-17, three innocent-looking integers, waiting for a well-meaning engineer to "honor" them.

The canonical, correct rule has not changed and will not change: **the sensor variant ALONE decides which stored slot feeds each channel. Never use `co`.** Output order is always RED, GREEN, NIR. Then:

- **Variant A** (flags bits 0-1 == 0): straight through. `slot0 = RED, slot1 = GREEN, slot2 = NIR`.
- **Variant B** (flags bits 0-1 == 1): the cost-down board. `slot0 = NIR, slot1 = GREEN, slot2 = RED`, i.e. **RED comes from slot2, GREEN from slot1, NIR from slot0.** (Yes, this is the mapping the re-bench corrected to; if you have an old note that says RED is at slot1 and GREEN at slot2, that note is superseded — see the Variant B section. RED is slot2.)
- **Variant C** (flags bits 0-1 == 2): defective lens batch, captures are unusable, quarantine as `sensor_variant_c`.

Notice that *every one of these is derivable from two bits.* You never need `co`. You never *want* `co`. The variant is the contract; `co` is noise.

### A worked example showing the damage

Let me make this concrete with a fictional Variant B unit, `RBX-7A2C`, capture `rbx-7a2c-0005.png`, deployed at `site-lagoon`. Here's a decoded blob (hand-built for the writeup, base64 stripped already, shown as hex with annotations):

```
52 42                      magic "RB"
02                         version 2
05                         flags = 0b00000101  -> variant bits = 01 = B ; nz bit2=1 -> nz[0]=1, nz[1]=0, nz[2]=0
00 05                      seq = 5
2A F8                      wb[0] = 0x2AF8 = 11000  -> 1.1000
27 10                      wb[1] = 0x2710 = 10000  -> 1.0000
1F 40                      wb[2] = 0x1F40 =  8000  -> 0.8000
04 02 06                   blk[0]=4, blk[1]=2, blk[2]=6
02 01 00                   co = [2,1,0]   <-- DEBUG. IGNORE.
08 52 42 58 2D 37 41 32 43 dev_len=8, "RBX-7A2C"
0B 73 69 74 65 2D 6C 61 67 6F 6F 6E   site_len=11, "site-lagoon"
?? ??                      crc16 trailer
```

**Correct decode (variant B mapping, `co` ignored):**

- RED comes from slot2. nz[2] == 0 (raw) so scale_RED = wb[2] = 0.8000 -> `0.800000`.
- GREEN comes from slot1. nz[1] == 0 (raw) so scale_GREEN = wb[1] = 1.0000 -> `1.000000`.
- NIR comes from slot0. nz[0] == 1 (normalized) so scale_NIR = wb[0] * (255 - blk[0]) / 255 = 1.1000 * (255 - 4) / 255 = 1.1000 * 251 / 255 = 1.082745... -> `1.082745`.

So the correct channel_scales are RED 0.800000, GREEN 1.000000, NIR 1.082745, and we feed planes in RED, GREEN, NIR order taken from slots 2, 1, 0 respectively.

**Devon's buggy decode (used `co = [2,1,0]` as the order):**

His code did `RED = slot[co[0]] = slot[2]`, `GREEN = slot[co[1]] = slot[1]`, `NIR = slot[co[2]] = slot[0]`. On *this particular* blob that happens to coincide with the correct Variant B mapping (slot2/slot1/slot0)! So `RBX-7A2C` actually decoded *fine* under the buggy code. That's the cruel part — the bug is invisible on exactly the units where `co` happens to agree with the variant.

Now take a Variant B sibling on a different board spin, `RBX-22E9`, `rbx-22e9-0011.png`, same site, where the bring-up harness was wired straight and `co` came out `[0,1,2]`:

```
52 42 02 05 00 0B          magic, v2, flags=0x05 (variant B, nz[0]=1)
2A F8 27 10 1F 40          wb = 1.1000, 1.0000, 0.8000
04 02 06                   blk = 4,2,6
00 01 02                   co = [0,1,2]   <-- DEBUG, and here it's identity
08 ...RBX-22E9... 0B ...site-lagoon... crc
```

**Correct decode:** still Variant B -> RED from slot2 (0.8000), GREEN from slot1 (1.0000), NIR from slot0 normalized (1.082745). Same as before; the variant is what matters, not `co`.

**Buggy decode:** `RED = slot[co[0]] = slot[0]`, `GREEN = slot[1]`, `NIR = slot[2]`. So the buggy pipeline fed RED <- slot0 (the NIR-carrying slot!), and NIR <- slot2 (the RED-carrying slot). **RED and NIR are transposed.** The model got a near-infrared plane where it expected red and vice versa. To a coral classifier that has learned that healthy coral is bright in red and dark-ish in NIR, this swap inverts the single most discriminative feature it has. Every prediction flipped toward "not coral." That's your 0.21.

So across the lagoon batch, the units where `co` was an identity-ish permutation got their RED/NIR swapped (wrong), and the units where `co` happened to match the variant mapping decoded correctly. The mix is what produced a *partial* but devastating accuracy crater, and what made it look (briefly, to the panicked) like "the model" rather than "the decoder."

### The second, nastier failure mode: miscounting the bytes

There's a subtler way `co` bites you, and it's the reason this section yells about "skip *exactly three* bytes."

The `co` triple is positional. Everything after it — `dev_len`, the device id, `site_len`, the site id, the CRC trailer — is found by *counting forward from where co ends*. The packed format has no delimiters and no field tags; it's purely "the next byte means X because of how many bytes came before it." So if your decoder skips the wrong number of bytes for `co`, you don't just get a wrong `co` (which you weren't using anyway) — **you shift the read cursor**, and every length-prefixed field after it reads from the wrong place.

Concretely, the failure modes we actually saw or reproduced:

- **Skip 2 instead of 3** (off-by-one, classic). After blk you're now positioned on `co[2]` thinking it's `dev_len`. `co[2]` might be `0` (zero-length device id — your device id comes out empty, dedup goes haywire because everything collides on `""`) or it might be some number like `2` or `6`, in which case you slice 2 or 6 bytes of *what is actually still co plus the start of the real dev_len byte* as your device id. You get a garbage device id, the wrong site, and almost certainly a CRC mismatch when you reach the trailer at the wrong offset.

- **Skip 4 instead of 3** (over-skip). You consume the real `dev_len` byte as if it were part of `co`, then read the first byte of the *device id ASCII* as your length. If the device id starts with "R" (0x52 = 82), congratulations, your decoder now tries to read an 82-byte device id and runs off the end of the blob. Truncation -> can't parse -> `bad_checksum`.

- **The "it still passed CRC!" trap.** This is the one that fooled us for an afternoon. Because the CRC is computed over *every preceding byte* up to the trailer, an off-by-N in how you *interpret* the bytes does NOT change the CRC if you still feed the same byte range into the CRC function and still land on the same trailer. Devon's original buggy code *read* `co` and used it for ordering but still advanced the cursor by 3, so the trailer was found correctly and CRC passed — that's why the corruption was semantic (wrong channels) rather than a clean `bad_checksum`. But a *different* buggy decoder that skips the wrong count will usually (not always!) desync enough to fail CRC, which at least fails loudly. The dangerous combination is "wrong semantics, right byte accounting": it sails through every integrity check and silently poisons inference. There is no checksum for "you used the debug field as if it were meaningful." The only defense is the rule: **never read `co`, skip exactly 3.**

If you want a one-line mental model: bytes 15, 16, 17 exist *only* to be skipped. Their entire job in your decoder is to advance the cursor by three. Read them into a variable if it makes your code clearer, sure, but that variable must die unused. The instant `co` influences a channel mapping, an offset, or anything else, you have a bug.

### Resolution / corrective actions

What we actually did, 2024-03-18 through 2024-03-20:

1. **Reverted Devon's "honor co" change.** Channel mapping is back to variant-only. (Devon took it well; the commit message was sincere and the instinct was good, the field was just lying to us.)
2. **Re-ran the entire lagoon batch and the two prior nights' batches** from raw PNGs through the corrected decoder. Spot-check top-1 went back to 0.87 on the lagoon set. No model weights were touched at any point — confirming, again, that it was the pipeline.
3. **Added a regression fixture.** We now carry a tiny fixture set of fictional blobs, including a Variant B unit whose `co` is `[0,1,2]` (identity) and a sibling whose `co` is `[2,1,0]`, both of which MUST produce identical RED/GREEN/NIR slot mappings. If a decoder change makes those two diverge, it's reading `co`, and the test fails. This is deliberately the exact pattern that hid the bug.
4. **Added an assertion in the decoder** (debug builds only): after parsing, we log a warning if `co` is anything other than `[0,1,2]`, NOT because non-identity `co` is wrong, but purely as a tripwire so that if someone reintroduces a dependency on it, the warning volume makes it obvious during review. The assertion never changes behavior.
5. **Killed the cheat-sheet line.** See below.

### About the old cheat-sheet (this advice is WRONG)

The single-page "ReefBox decode cheat-sheet" that floated around in the team drive in 2023 had a line in the "channel mapping" box that read, roughly:

> *"Channel order: read co (bytes 15-17) and reorder slots to RED/GREEN/NIR per co. Variant only tells you the board, co tells you the order."*

**That line is wrong. Do not follow it.** It is, as far as we can reconstruct, the original sin that Devon's change was faithfully implementing — he wasn't freelancing, he was doing what the cheat-sheet said. The cheat-sheet conflated "co is named channel-order" with "co is *the* channel order," and nobody had stress-tested it on a board spin where `co` disagreed with the variant. The two real authorities, in order, are: (a) the sensor **variant** for slot→channel mapping, full stop; and (b) the per-channel `nz` flags + `wb`/`blk` for scale. `co` is on neither list. We've struck the line and the cheat-sheet now just says "co (bytes 15-17): DEBUG. Skip exactly 3 bytes. Never use." Per the reading convention, this errata wins over the cheat-sheet; trust the errata, not the cheat-sheet.

If you find a *copy* of the old cheat-sheet anywhere — printed, in a fork, pasted into someone's onboarding doc — fix or delete that line. The number of times a single stale sentence has re-spawned this exact incident in adjacent teams is genuinely depressing.

### Quick checklist before you trust a decode

- [ ] Did you decide RED/GREEN/NIR slot mapping from the **variant bits** (flags 0-1) and nothing else?
- [ ] Did you compute scale from `nz[s]` + `wb[s]` (+ `blk[s]` when normalized), rounded to 6 dp?
- [ ] Did your cursor advance by **exactly 3** for the `co` triple?
- [ ] Is `co` referenced *nowhere* in your mapping or offset logic?
- [ ] Does your Variant B mapping put RED at slot2, GREEN at slot1, NIR at slot0?
- [ ] If you swapped a Variant B unit's `co` to `[0,1,2]` or `[2,1,0]`, would your output be byte-for-byte identical? (It must be.)

If all six are yes, `co` can't hurt you. If any is no, you're one stale board spin away from a 0.21 night.

— *Priya, 2024-05-02. Appended note (Sam, 2024-06-11): we hit a near-miss on a Variant A unit where someone "validated" co was `[0,1,2]` and concluded co was therefore safe to use generally. It is not safe to use, ever, even when it's identity. Identity co is a coincidence, not a contract. Skip the three bytes.*
## Field corrections (logged as we found them)

> Housekeeping note before the list, because people keep getting bitten: this is the errata block. If anything below contradicts the Quick Reference Card (the v1.0 cheat-sheet near the front of this notebook), or contradicts some older journal entry, **the errata win.** That is the whole point of an erratum. We date them so the ordering is unambiguous — when two entries fight, the one with the later date is the truth. Trust the errata, not the cheat-sheet. The cheat-sheet was written fast, in a hotel, before anybody had actually pulled a `tEXt` chunk apart byte by byte, and it shows.
>
> I am collecting these into one place (this section) because we were tired of new hires re-discovering the same five potholes. If you only read one section of this notebook before touching the decoder, read this one. Then go read sections 4 and 5 for the full byte layout and the scale math.

A short table of contents for this block, so you can jump:

- **ERRATA-009** — the `tEXt` value is packed binary, not `key=value` text.
- **ERRATA-011** — integers are big-endian, not little-endian.
- **ERRATA-012** — `wb` fixed-point is ×10000, not ×1000.
- **ERRATA-014** — the trailer is a CRC-16/CCITT-FALSE, not a byte sum; failing it is `bad_checksum`.
- **ERRATA-016** — Variant B mapping corrected (RED←slot2, GREEN←slot1, NIR←slot0); Variant A reaffirmed.
- **ERRATA-017** — the `co` bytes are debug junk; skip them.
- **ERRATA-018** — site registry (`allowed_sites`); unrecognized site → `unknown_site`; we now have FIVE quarantine reasons in a fixed order.
- **ERRATA-020** — `input_size` is pulled out of default precedence (site > global only); there are now THREE exception fields.

(ERRATA-010, -013, -015, and -019 were about firmware flashing rigs, a label-studio export bug, the dock charger recall, and a typo in the shipping form. None of them touch the decode path, so they're filed in the hardware binder, not here. Don't go looking for them in this section.)

---

### ERRATA-009 (2024-02-19)

This is the big one, and it's the one that wasted the most engineer-hours, so it goes first.

The cheat-sheet says — and I quote the v1.0 card — *"the chunk value is just base64 of the old `key=value` text; decode it and you'll see `wb=...;blk=...;dev=...` like the 1.0 sidecar files."* **That is wrong.** It was true for a couple of pre-production loaner units that never shipped, and somebody wrote the card off those. The shipping firmware does not do that.

What is actually in the `tEXt` chunk value: a base64 string. Decode the base64 and you do **not** get text. You get a **packed binary blob**. There are no `=` signs, no semicolons, no field names inside it. It is a fixed binary structure — magic bytes, a version byte, a flags byte, fixed-point integers, length-prefixed strings, and a trailing checksum. The byte-by-byte layout is in section 4; I am not going to repeat the whole thing here, but the headline is: **after the base64 decode, parse BYTES, not characters.**

How to tell you've fallen into the trap: if your decoder is doing something like `split on ";"` or `split on "="` or running a regex for `wb=` over the decoded value, you are parsing binary as if it were text and you will get garbage (or, worse, plausible-looking garbage). The very first two decoded bytes are the ASCII letters `RB` (0x52 0x42) — the magic. If you base64-decode the value and the first two bytes are `RB`, you are looking at the real binary block. If you base64-decode and immediately see something like `wb=1.0` you are either looking at one of those dead loaner units (you won't — none shipped) or you've grabbed the wrong key.

Worked sanity check, fictional unit `RBX-7A2C`: its `reefbox:calibration` value starts `UkIC...` in base64. Decode the first chunk and the leading bytes are `52 42 02 ...` → `R`, `B`, then version byte `0x02`. That `RB` is your proof you're on the binary path. Anybody who saw `UkIC` and went "hm, that's not readable text, the chunk must be corrupt" was wrong twice: it's not text, and it's not corrupt.

One more thing this clears up, since it confused a couple of people: there are two metadata keys that can carry the block, `reefbox:calibration` (the 2.x firmware, **authoritative**) and `rbx:cal` (legacy 1.x, fallback only). *Both* of them, when present, hold the same packed-binary-base64 format described here — the version byte inside the blob (1 vs 2) tells you which firmware wrote it, but the byte layout is identical either way. The keys are not "one text, one binary." They're both binary. So the rule "decode base64 → parse bytes" applies no matter which key you read from. (Which key wins when both are present is covered in section 4 — short version, the 2.x `reefbox:calibration` block wins and the leftover `rbx:cal` is ignored — but that's a separate concern from "is it text or binary." It's binary. Always.)

Supersedes: Quick Reference Card §"format", bullet (a).

---

### ERRATA-011 (2024-03-04)

The Quick Reference Card says the multi-byte integers in the blob are little-endian. **They are not. Every multi-byte integer in the calibration blob is BIG-ENDIAN (network byte order, most-significant byte first).**

This matters for the two `uint16` fields:

- `seq` at bytes 4–5, and
- each of the three `wb` entries (`wb[0]` at bytes 6–7, `wb[1]` at 8–9, `wb[2]` at 10–11).

The single-byte fields (`version`, `flags`, the three `blk` bytes, the `co` bytes, the two length bytes) have no endianness — a byte is a byte — so those were never affected. It's purely the `uint16`s that the cheat-sheet got backwards.

How the bug shows up: if you read big-endian values as little-endian you get the bytes swapped, and a `wb` that should be a sensible fixed-point number comes out enormous or tiny. Example, fictional: suppose `wb[0]` is stored as bytes `27 10`. Read **big-endian** that's `0x2710` = 10000, which divided by 10000 (see ERRATA-012, below) is `1.0000` — a perfectly normal white-balance gain. Read it **little-endian** and you'd get `0x1027` = 4135, i.e. `0.4135`, which is wrong and will quietly dim that channel by more than half. No crash. Just bad numbers feeding the classifier. Those are the worst kind of bug, so: **big-endian. MSB first.**

Concretely, to read a `uint16` at offset `o`: `value = (byte[o] << 8) | byte[o+1]`. The first byte you read is the high byte. If your language has a "read uint16 big-endian" / "network order" / "`>H`" option, use it and move on.

Supersedes: Quick Reference Card §"format", bullet (b). Also supersedes the offhand "they're probably LE like everything else on x86" comment in the early journal entry from January — no, the firmware author serialized in network order on purpose.

---

### ERRATA-012 (2024-03-04)

Filed the same day as ERRATA-011 because we found them together while staring at the same hex dump.

The cheat-sheet says white-balance gains are stored as fixed-point "times 1000," so you'd divide by 1000 to get the float. **Wrong. The scale factor is 10000, not 1000. Each `wb` entry is stored as `round(wb * 10000)` in a big-endian `uint16`; to recover the float you divide by 10000.**

So the full recovery for a `wb` slot is:

1. Read the two bytes big-endian (per ERRATA-011) → a `uint16`.
2. Divide by **10000.0**.

Why this is easy to get wrong: with the ÷1000 reading, a stored `0x2710` (= 10000) comes out as `10.0`, which is a ridiculous gain but not *obviously* ridiculous to someone who's never seen a normal value. With the correct ÷10000 it comes out as `1.0`, which is exactly the kind of near-unity gain white balance should be. The factor-of-ten error inflates every channel's scale by 10×, and because it hits all channels it doesn't even produce a color cast you'd notice by eye — the whole frame just blows out. Sneaky.

Worked fictional values for unit `RBX-22E9`, the three `wb` slots stored as:

| slot | bytes (hex) | uint16 (big-endian) | ÷ 10000 |
|------|-------------|---------------------|---------|
| 0    | `27 10`     | 10000               | 1.0000  |
| 1    | `25 22`     | 9506                | 0.9506  |
| 2    | `2A F8`     | 11000               | 1.1000  |

All three land in the "near 1.0" neighborhood, which is the smell test: recovered `wb` values should generally be within shouting distance of 1. If yours are coming out near 10, you divided by 1000. If they're coming out near 0.1, you multiplied somewhere you should have divided.

The `uint16` ceiling is 65535, i.e. a stored gain up to `6.5535` — we have never seen anything above ~1.4 in the field, but the headroom is there.

Supersedes: Quick Reference Card §"format", bullet (c).

---

### ERRATA-014 (2024-04-22)

The last two bytes of every blob are a checksum. The cheat-sheet claims it's "just the 8-bit sum of all the preceding bytes, in the last byte" (and is fuzzy about why there are two trailing bytes at all). **Wrong on both counts.** The trailer is a **16-bit CRC**, occupying the final two bytes as a big-endian `uint16`, and it is specifically **CRC-16/CCITT-FALSE**.

The exact parameters — write these down, because "CRC-16" alone is ambiguous and there are a dozen incompatible variants:

- **Polynomial:** `0x1021`
- **Init:** `0xFFFF`
- **Input reflection:** none (process each byte MSB-first)
- **Output reflection:** none
- **Final XOR:** `0x0000` (i.e., none)

Confirm your implementation before you trust it: the CRC-16/CCITT-FALSE **check value over the ASCII string `123456789` is `0x29B1`.** If your routine produces `0x29B1` for `"123456789"`, it's correct. If it produces anything else (e.g. `0x2189`, `0x31C3`, `0xE5CC`, `0x4B37` — all real outputs of *other* CRC-16 variants over that same string), you've picked the wrong variant; fix it before you run a single capture, or you will mis-quarantine good data and pass bad data.

How to use it on a capture: compute the CRC-16/CCITT-FALSE over **every byte of the blob except the final two** (magic through the end of the site string), then compare your computed value against the trailing `uint16` (read big-endian, per ERRATA-011). If they match, the block is intact. If they do **not** match, the block is corrupt or truncated, and **the capture is quarantined with reason `bad_checksum`.** This replaces the old hand-wave of "if it looks weird, skip it" — there's now a precise, deterministic test.

Note this also gives us a real second quarantine reason. The cheat-sheet's three-reason list (see ERRATA-018 for the full correction) never mentioned `bad_checksum` at all, because it thought the checksum was a trivial byte-sum nobody bothered to verify. Now we verify it, and a failure is its own reason code.

A worked fictional negative case: `RBX-7A2C` capture `rbx-7a2c-0005.png` came off a flaky reader with one byte flipped in the `site` string. Recomputed CRC = `0x8C4E`; stored trailer = `0x8C2E`. Mismatch → `bad_checksum`. We did **not** try to "guess" the right site and salvage it; a CRC failure means the bytes are untrustworthy, full stop, so the whole block is out.

One more gotcha that surfaced while writing the CRC code: include the magic bytes and the version byte in the CRC. The CRC covers **all** preceding bytes, not just "the payload." Off-by-a-couple at the front will make every block fail.

Two implementation footguns we actually hit, so you don't:

- **"CRC-16" is not enough information.** The first pass of our decoder used a generic "CRC-16" library default, which turned out to be CRC-16/ARC (poly `0x8005`, reflected, init `0x0000`). It produced `0xBB3D` over `"123456789"`, not `0x29B1`, and so it flagged *every* good block as `bad_checksum`. We quarantined an entire survey before someone ran the check string. Always run the `0x29B1` check.
- **Don't accidentally reflect.** CCITT-FALSE is the *non-reflected* variant. If you start from a reflected implementation and "fix" it by reversing bytes, you'll pass the check string by luck on some inputs and fail others. Use a real CCITT-FALSE routine: MSB-first, no in/out reflection, init `0xFFFF`, final XOR `0x0000`.

And to be unambiguous about scope: `bad_checksum` covers both "the CRC doesn't match" **and** "the block won't decode at all" — wrong magic (the first two bytes aren't `RB`), a truncated blob that runs out of bytes before the trailer, a `dev_len`/`site_len` that points past the end. Anything where the bytes present don't form a parseable, CRC-valid block is `bad_checksum`. The only thing that *isn't* `bad_checksum` is when there's no block at all under either key — that's `missing_calibration` (see ERRATA-018).

Supersedes: Quick Reference Card §"integrity", bullet (d).

---

### ERRATA-016 (2024-06-10)

This one corrects an earlier *correction*, so read carefully — there were three states of belief and only the last is right.

Background: the canonical output order is always **RED, GREEN, NIR**. The sensor **variant** (the low two bits of the flags byte) alone decides which stored slot feeds each output channel. (Do **not** use the `co` triple for this — see ERRATA-017.) The variant-to-slot mapping is a fixed property of the board, not something encoded per-capture.

**Variant A — reaffirmed, unchanged:** straight through. `slot0 → RED`, `slot1 → GREEN`, `slot2 → NIR`. Nobody ever got A wrong; I'm reaffirming it only so there's no doubt that *this* erratum doesn't touch A. A is fine. A was always fine.

**Variant B — corrected.** Here's the history so you understand why there's confusion in older entries:

1. The Quick Reference Card lumped B in with A and said "all variants read straight through" (slot0=RED, slot1=GREEN, slot2=NIR). That was the first wrong belief.
2. An early hardware write-up corrected that to "B has the visible channels swapped: RED from slot1, GREEN from slot2, NIR from slot0." That was the *second* belief and it was **also wrong** — it correctly figured out that NIR is wired to slot0 on the cost-down board, but it transposed the two visible channels.
3. **The latest re-bench (this erratum) is the truth:** on Variant B, the cost-down board wires the NIR photosite into the **first** stored slot, and the two visible channels land as **GREEN in slot1, RED in slot2**. So:

   - **RED comes from slot2**
   - **GREEN comes from slot1**
   - **NIR comes from slot0**

To be explicit, because this is the single most-missed rule in the whole notebook: the previous "RED from slot1 / GREEN from slot2" mapping is **superseded**. RED is **slot2**, GREEN is **slot1**. The re-bench transposed the two visible channels relative to that older note. If your decoder still has B reading RED from slot1, it's running the obsolete mapping and your reds and greens are swapped on every B unit.

Mapping table, both variants, for reference (C is below):

| output channel | Variant A slot | Variant B slot |
|----------------|----------------|----------------|
| RED            | slot0          | **slot2**      |
| GREEN          | slot1          | slot1          |
| NIR            | slot2          | **slot0**      |

Why it was hard to catch by eye: GREEN is in slot1 for *both* A and B, so a Variant-B capture decoded with the A mapping (or with the obsolete B mapping) still gets GREEN right — only RED and NIR are wrong, and NIR isn't something a human reviewer eyeballs. So the classifier degrades on B units without an obvious "the image is pink" tell. The re-bench was done on a calibrated target precisely because eyeballing wasn't catching it.

Worked fictional Variant-B example, unit `RBX-7A2C`, recovered per-slot values `wb = [0.91, 0.96, 1.08]`, `blk = [2, 1, 3]`, `nz = [1, 1, 1]` (all normalized). Apply the **current** B mapping and compute scale `wb[s]*(255-blk[s])/255` per the formula in section 5:

- RED ← slot2: `1.08 * (255-3)/255 = 1.08 * 252/255 = 1.067294` (round 6dp).
- GREEN ← slot1: `0.96 * (255-1)/255 = 0.96 * 254/255 = 0.956235`.
- NIR ← slot0: `0.91 * (255-2)/255 = 0.91 * 253/255 = 0.902863`.

If you'd used the old "RED from slot1" mapping you'd have handed RED the slot1 numbers (`0.956235`) and NIR... well, the old note had NIR at slot0 too, so NIR would have matched, but RED and GREEN would be swapped. Wrong reds, wrong greens, same green-looking number by coincidence. Use slot2 for RED.

**Variant C — unchanged, restated for completeness:** Variant C is the defective lens batch. Those captures are **unusable**; there is no salvage and no mapping. A Variant-C capture is quarantined with reason `sensor_variant_c`. (This erratum doesn't change C; I mention it so nobody reads "B was corrected" and wonders whether C moved too. It didn't.)

Supersedes: Quick Reference Card §"channels", bullet (e), *and* the earlier hardware write-up's "RED from slot1" Variant-B mapping. Variant A and Variant C statements are reaffirmed unchanged.

---

### ERRATA-017 (2024-06-11)

Filed the day after ERRATA-016 because the re-bench made it painfully clear what the `co` bytes are *not*.

The blob carries three bytes — `co[0]`, `co[1]`, `co[2]` at bytes 15, 16, 17 — that look like a channel-order permutation. The Quick Reference Card said to read them and reorder channels accordingly. **Do not.** The `co` triple is a leftover **debug** dump from the firmware bring-up; it does not describe the real channel order and on some boards it's just stale or zeroed. The real channel order comes from the **sensor variant** (ERRATA-016), period.

So the rule is: **skip the three `co` bytes entirely.** Read them off the wire so your byte offset advances correctly, then throw them away. Never feed `co` into the mapping. (There's a full incident writeup — INC-2231 — about an engineer who reordered channels from `co` and watched accuracy crater. Go read it if you want the gory version.)

The *other* reason this erratum matters, beyond "don't use co for ordering": the `co` bytes are exactly **three** bytes wide, and they sit **between** the `blk` triple and the `dev_len` byte. If you miscount them — skip two, or skip four — every offset after them is wrong: `dev_len` reads the wrong byte, the device id string comes out mangled, `site_len` is garbage, and the CRC fails on a block that was actually fine. So "skip `co`" specifically means "advance past exactly bytes 15, 16, and 17, then continue at byte 18 with `dev_len`." Skip three. Not two, not four. Three.

Fictional illustration, the bytes around `co` for `RBX-22E9`:

```
... 0E 01 03   04 01 02   05  52 42 58 2D 32 32 45 39 ...
    \blk[0..2]/ \co[0..2]/ ^^  \---- "RBX-22E9" ----/
                           dev_len = 0x05 = 5
```

Here `co = [04, 01, 02]`. It looks like a permutation — and a tempting one — but it's debug noise. Ignore it. The `dev_len` byte is `0x05`, so the next 5 ASCII bytes `52 42 58 2D 32 32 45 39` spell `RBX-22E9` (that's 8 bytes — bad example length on my part, treat the dev_len as whatever it actually is; the point is you only land on it correctly if you skipped exactly three `co` bytes first). The takeaway stands: skip three, don't use them.

Supersedes: Quick Reference Card §"channels", bullet (e), the "use the co triple" half.

---

### ERRATA-018 (2024-08-05)

The Quick Reference Card lists exactly three quarantine reasons: `missing_calibration`, `sensor_variant_c`, `superseded`. **That list is incomplete.** Between ERRATA-014 (which added `bad_checksum`) and this erratum (which adds `unknown_site`), we now have **five** reason codes, and — equally important — a **fixed evaluation order**.

First, the new rule this erratum actually introduces: the **site registry**. `global.yaml` now carries an `allowed_sites` list — the registry of site ids we recognize as real, surveyed, model-supported sites. The site for a capture is the `site` field decoded out of its calibration blob (the length-prefixed ASCII string near the end). **If a capture's decoded site is not in `allowed_sites`, the capture is quarantined with reason `unknown_site`.** We added this after a capture came in tagged for a site that didn't exist in any model card — turned out to be a typo'd `site` baked into a field-flashed unit (think `site-ghost`, the obviously-fake placeholder we use in examples). Rather than silently inventing settings for a site we know nothing about, we quarantine it.

Now the complete, current quarantine reason set — **five tokens**:

1. `missing_calibration` — neither calibration key (`reefbox:calibration` nor `rbx:cal`) is present on the PNG.
2. `bad_checksum` — a calibration block is present but won't decode, or its recomputed CRC-16/CCITT-FALSE doesn't match the trailer (corrupt/truncated). (Added by ERRATA-014.)
3. `sensor_variant_c` — the sensor variant is C (defective lens batch; unusable).
4. `unknown_site` — the decoded site is not in `global.yaml`'s `allowed_sites`. (Added by *this* erratum.)
5. `superseded` — lost the same-device dedup: an older `seq` for a `dev` that also has a newer capture.

**Evaluation order is fixed and you must apply it in this sequence:**

```
missing_calibration  →  bad_checksum  →  sensor_variant_c  →  unknown_site  →  superseded
```

First match wins. **Each capture gets exactly one reason** — the first one that applies in that order. This ordering is not cosmetic; it changes outcomes. Example: a capture that is both a corrupt block *and* (if it could be decoded) a Variant C, or both an unknown site *and* a superseded duplicate — the earlier reason in the chain is the one recorded. You can't even know a capture's site or variant until you've successfully decoded it, which is *why* `missing_calibration` and `bad_checksum` come first: no block, or an un-decodable block, means there's nothing downstream to evaluate. Then variant (a property of the bytes), then site (needs the registry), then dedup (needs all the survivors to compare `seq`).

A couple of worked dispositions, all fictional:

- `RBX-7A2C` cap `...-0005.png`: block present, CRC fails. → `bad_checksum`. We never even look at its site or variant.
- A capture on Variant C whose site happens to be `site-ghost` (not in `allowed_sites`): variant C is checked **before** site, so → `sensor_variant_c`, not `unknown_site`.
- A capture with a valid block, Variant A, site `site-lagoon` (which *is* in `allowed_sites`), but it's the older of two `seq`s for the same `dev`: passes missing/checksum/variant/site, fails dedup → `superseded`.

And the standing rule, restated because it's easy to forget under deadline: **never drop a capture silently.** Everything that doesn't make it into the manifest's `devices` array lands in the `quarantined` array with one of these five reasons.

Supersedes: Quick Reference Card §"quarantine", bullet (h) (the "three reasons" list). The two earlier-added reasons — `bad_checksum` (ERRATA-014) and now `unknown_site` — bring the total to five, in the order given above.

---

### ERRATA-020 (2024-10-14)

Last one in this block, and it's about the YAML model cards, not the binary blob.

Inference settings come from three YAML layers: `global.yaml` (baseline), `sites/<site>.yaml` (per-site), and `devices/<dev>.yaml` (per-device). The Quick Reference Card said, flatly, "the device card always wins for every field." **That's too broad.** The default merge precedence is **device > site > global**, but that default applies to **only two fields**: `model_name` and `model_version`. For everything else there are now **exception** fields where the default does *not* hold.

As of this erratum there are **THREE exception fields**. Listing all three together so they're in one place:

1. **`confidence_threshold`** — device thresholds are untrusted (there's a firmware bug that writes a bogus threshold into some device cards). Resolved **site > global only; the device value is ignored.** (This exception predates this erratum; restated here for the full picture.)
2. **`input_size`** — **this is the field ERRATA-020 actually adds to the exception list.** Input size is a function of the per-site mount geometry (the housing/lens distance at a given site), not of the individual camera. So `input_size` is resolved **site > global only; the device value is ignored.** A device card that specifies an `input_size` is overruled — the site (or, failing that, global) decides. In the manifest it's emitted as `[w, h]`.
3. **`labels_version`** — centrally pinned for reproducibility. For an ordinary site it is **taken from `global.yaml`**; site and device values are ignored. *(pilot sites are the one exception — there is one documented pilot-site exception, spelled out in the 2026-03-18 carve-out later in the label-governance memo.)* (Predates this erratum; restated.)

So the resolution rules, all together:

| field | resolution |
|-------|------------|
| `model_name` | device > site > global (default) |
| `model_version` | device > site > global (default) |
| `confidence_threshold` | **site > global** (device ignored) |
| `input_size` | **site > global** (device ignored) — *new in ERRATA-020* |
| `labels_version` | **global** (site & device ignored) — *except pilot sites, which take it from the site card; see the label memo* |

Why `input_size` moved: we shipped a manifest where a device card's `input_size` of `[640, 640]` overrode the site's `[768, 512]`, and the classifier — which had been tuned per-site for the mount geometry — produced worse boxes on that one camera. The device should never have had a say in input size; it's the site's mount that determines framing, not the camera body. So we pulled it out of the default chain. If a device card and a site card disagree on `input_size`, the **site** wins; if neither exists, fall back to `global`. The device value is dropped on the floor regardless.

Worked fictional resolution for a device at `site-pinnacle`:

- `global.yaml`: `model_name: reefnet-coastal`, `model_version: 1.2.0`, `confidence_threshold: 0.50`, `input_size: [640, 640]`, `labels_version: 7`, `allowed_sites: [site-lagoon, site-pinnacle, ...]`.
- `sites/site-pinnacle.yaml`: `model_version: 1.3.0`, `confidence_threshold: 0.60`, `input_size: [768, 512]`.
- `devices/<dev>.yaml`: `model_name: reefnet-coastal-xt`, `confidence_threshold: 0.80`, `input_size: [512, 512]`, `labels_version: 9`.

Resolved:

- `model_name` → `reefnet-coastal-xt` (device wins — default precedence).
- `model_version` → `1.3.0` (no device value; site wins over global).
- `confidence_threshold` → `0.60` (site > global; device's `0.80` **ignored** — exception).
- `input_size` → `[768, 512]` (site > global; device's `[512, 512]` **ignored** — exception, this erratum).
- `labels_version` → `7` (global only; device's `9` and any site value **ignored** — exception).

Note how only `model_name` and `model_version` actually honor the device card. If your merge logic is letting the device override `input_size`, `confidence_threshold`, or `labels_version`, it's running the obsolete "device always wins" rule from the cheat-sheet.

Supersedes: Quick Reference Card §"model cards", bullet (f) (the blanket "device card always wins"). Together with the pre-existing `confidence_threshold` and `labels_version` exceptions, this makes **three** exception fields. Default precedence (device > site > global) now applies to `model_name` and `model_version` only.

---

> **Closing reminder for this errata block.** If you take nothing else from section 8: the chunk value is **packed binary** (decode the base64, then parse bytes); integers are **big-endian**; `wb` is fixed-point **÷10000**; the trailer is **CRC-16/CCITT-FALSE** (check `0x29B1` over `123456789`) and a mismatch is **`bad_checksum`**; Variant B is **RED←slot2, GREEN←slot1, NIR←slot0** (Variant A straight-through unchanged); **skip the three `co` bytes**; an unrecognized `site` is **`unknown_site`** and there are **five** quarantine reasons in the order missing_calibration → bad_checksum → sensor_variant_c → unknown_site → superseded; and `input_size` is **site > global only** (device ignored), one of **three** exception fields alongside `confidence_threshold` and `labels_version`. Everything the v1.0 cheat-sheet says that contradicts the above is dead. Trust the errata.
## Model cards: global, site, and device layers

Okay. By now you've decoded the calibration block out of the PNG, you know which slot feeds RED/GREEN/NIR, and you've computed the channel scales. That gets you *half* of a manifest row. The other half — the model name, the model version, the input size, the confidence threshold, the labels version — does NOT live in the camera at all. It lives in a little stack of YAML files we keep in the repo under `cards/`, and the manifest builder has to *merge* those layers per device to figure out the final settings. This section is about that merge.

A warning up front, because people keep getting this exact thing wrong: the merge rule is **not** "device wins, end of story." That was the original cheat-sheet line and it is dead (see the ERRATA block, esp. the input_size and threshold corrections). The default device-beats-site-beats-global precedence now applies to **only two fields**: `model_name` and `model_version`. Three other fields — `confidence_threshold`, `input_size`, and `labels_version` — each resolve by their own special rule. If you treat the cards as a single uniform "deep merge where the most specific layer wins," you will produce a manifest that looks plausible and is wrong on three columns. We have shipped that bug. Twice. Don't be the third.

This section lays out the three layers, where the site for a device comes from, the `allowed_sites` registry, and the default precedence with a worked merge example for the two fields it actually governs. The three exception fields each get a full section of their own later (PM-4471 covers `confidence_threshold` and `input_size`; the label-governance memo covers `labels_version`); here I'll only point at them so you know they exist and don't try to fold them into the default rule.

### The three layers

There are exactly three YAML layers, from least specific to most specific:

1. **`global.yaml`** — the baseline. One file. Every field has a value here. Think of it as "what a brand-new device at a brand-new site gets if nobody has overridden anything." It also carries the `allowed_sites` list — more on that below — which is the only thing in `global.yaml` that isn't a per-field default.
2. **`sites/<site>.yaml`** — one file per survey site. The `<site>` in the filename matches a site id, e.g. `sites/site-lagoon.yaml`. A site card overrides the global baseline for the fields it lists. It does **not** have to list every field; it lists only the ones that differ from global for that site. Anything it doesn't mention falls through to global.
3. **`devices/<dev>.yaml`** — one file per device, keyed by the device id, e.g. `devices/rbx-7a2c.yaml`. Same deal: it overrides for the fields it lists and stays silent on the rest. Most device cards are tiny — often just a `model_version` bump because that one camera got a newer model pushed to it.

A few practical notes about the files themselves:

- **Sparse is normal.** Site and device cards are *overlays*, not full copies. A device card with just two lines in it is completely normal and correct. Do not "fill in" the missing fields from some template — missing means "inherit," and which layer you inherit from depends on the field.
- **`global.yaml` is the floor.** Every field that ends up in the manifest must be resolvable from `global.yaml` even if no site or device mentions it. If you ever find a field that's missing from `global.yaml`, that's a bug in the card repo, not something the manifest builder should paper over.
- **Filenames are lowercased.** The decoded device id might come out of the binary blob as `RBX-7A2C`, but the card file is `devices/rbx-7a2c.yaml`. Same for sites. Match case-insensitively when you go looking for the overlay file. (We've had "no device card found" mysteries that were purely a casing mismatch. The decoder preserves whatever ASCII was packed; the card repo is conventionally lowercase.)
- **A missing card is not an error.** If `devices/rbx-7a2c.yaml` doesn't exist, that just means this device has no device-level overrides. Same for a site with no `sites/<site>.yaml`. You resolve from whatever layers *do* exist. The only "site" thing that can fail a capture is the `allowed_sites` registry check, which is a separate gate (see below and the quarantine section), not "is there a YAML file."

Here's roughly what the three files look like. These are **fictional** values — do not copy them as ground truth, they're just to show the shape:

```yaml
# cards/global.yaml
model_name: reefnet-coastal
model_version: "4.0.0"
input_size: [512, 512]
confidence_threshold: 0.35
labels_version: labels-2026.02
allowed_sites:
  - site-lagoon
  - site-pinnacle
  - site-trench
  - site-shelf
```

```yaml
# cards/sites/site-pinnacle.yaml
# Pinnacle gets a bigger crop because the mount sits further back.
model_version: "4.1.0"
input_size: [768, 768]
confidence_threshold: 0.30
```

```yaml
# cards/devices/rbx-7a2c.yaml
# This unit was hand-pushed the deep model after the May refit.
model_name: reefnet-deepcoastal
model_version: "4.2.0"
confidence_threshold: 0.55   # <-- looks authoritative. it is NOT trusted. see PM-4471.
```

Notice that `site-pinnacle.yaml` doesn't mention `model_name` or `labels_version`, and `rbx-7a2c.yaml` doesn't mention `input_size`. That's the normal sparse-overlay pattern. Notice also that the device card *does* set a `confidence_threshold` — and that's exactly the kind of value you must learn to **ignore**, because thresholds at the device layer are not trusted. We'll get to why.

### A device's site comes from the decoded block, not from a card

This trips people up, so it gets its own paragraph. **The site for a device is the `site` field you decoded out of the calibration block** (the `site_len`-prefixed ASCII string near the end of the binary, right after the device id). It is *not* something you read out of a YAML card, and it is *not* something you infer from which `sites/*.yaml` files happen to exist.

So the flow is:

1. Decode the block → you get `dev` (device id) and `site` (site id) as ASCII strings, along with everything else.
2. That decoded `site` is the device's site. Full stop. It's also the value that goes in the manifest row's `site` field.
3. To resolve cards, you load `sites/<that decoded site>.yaml` (if it exists) and `devices/<that decoded dev>.yaml` (if it exists), plus `global.yaml`.

Because the site is whatever the camera says it is, a camera can claim a site that we don't actually run surveys at — a typo in provisioning, a unit that got physically moved without its config being updated, a test rig that was never re-flashed. That's what `allowed_sites` is for.

### The `allowed_sites` registry

`global.yaml` carries a list called `allowed_sites`. That list is the **registry of recognized sites** — the authoritative roster of survey locations we actually operate. It is the *only* place the registry lives; site cards don't self-register, and there is no separate registry file.

The rule: after you decode a capture's `site`, you check whether that site string is in `global.yaml`'s `allowed_sites`. If it is **not** listed, the capture is quarantined with reason `unknown_site`. If it **is** listed, the capture is eligible to be included (subject to the other quarantine checks and dedup).

Two things to keep straight:

- `allowed_sites` is the gate for whether a *capture* is recognized. The presence or absence of a `sites/<site>.yaml` *card* is a separate question entirely. A site can be in `allowed_sites` and have **no** site card — that's fine, it just means that site uses the global defaults for everything. What you must NOT do is treat "there's no site YAML" as "unknown site." The unknown-site test is purely "is this site string in the `allowed_sites` list in `global.yaml`."
- `unknown_site` is one of the five quarantine reasons, and it's evaluated in a specific order relative to the others (after `missing_calibration`, `bad_checksum`, and `sensor_variant_c`, before `superseded`). Don't re-litigate that ordering here — the quarantine section is the source of truth for it. Just know that the registry check is *why* `unknown_site` exists, and that the registry lives in `global.yaml`.

For a concrete fictional example: suppose `global.yaml` lists `allowed_sites: [site-lagoon, site-pinnacle, site-trench, site-shelf]`, and a capture decodes with `site = site-ghost`. `site-ghost` isn't on the list, so that capture is quarantined `unknown_site` — even if there happened to be a leftover `sites/site-ghost.yaml` lying around in the repo. The registry wins; the stray card means nothing.

### The DEFAULT precedence: device > site > global (for `model_name` and `model_version` ONLY)

Now the merge itself. For the two fields that follow the default rule — `model_name` and `model_version` — you resolve each field independently by walking from most specific to least specific and taking the first layer that *sets* it:

> **device card → site card → global**

Field by field:

- If the **device** card sets the field, use the device value. Done.
- Else if the **site** card sets the field, use the site value. Done.
- Else use the **global** value (which always exists).

Per-field, not per-file. This matters: a device card can win `model_version` while staying silent on `model_name`, in which case `model_name` keeps walking down to the site or global layer. You do **not** take "the whole model config from the most specific card that has anything." You resolve each field on its own.

And again, to hammer it: this default rule is **scoped to `model_name` and `model_version`.** The moment you reach for `input_size`, `confidence_threshold`, or `labels_version`, you switch to that field's special rule. Do not apply device-beats-site-beats-global to those three. (Mechanically, in the jq/yq merge, the cleanest approach is: resolve `model_name` and `model_version` with the device→site→global fallback, and resolve the other three with their own expressions. Don't write one generic "deep merge, deepest wins" and hope — it will overwrite `input_size` and `confidence_threshold` from the device card and pull `labels_version` from the wrong layer.)

### Worked merge example (`model_name` / `model_version`)

Let's merge a fully fictional device. Say we decoded a capture and got:

- `dev = RBX-7A2C`
- `site = site-pinnacle`

Both `site-pinnacle` is in `allowed_sites` (good — not quarantined for site), and the variant decoded to A or B (usable). So this one is heading for the `devices[]` array, and we need its model card.

The three layers, fictional:

```yaml
# cards/global.yaml (relevant lines)
model_name: reefnet-coastal
model_version: "4.0.0"
```

```yaml
# cards/sites/site-pinnacle.yaml
model_version: "4.1.0"
# (no model_name here)
```

```yaml
# cards/devices/rbx-7a2c.yaml
model_name: reefnet-deepcoastal
model_version: "4.2.0"
```

Resolve **`model_name`** (device → site → global):

- Device card sets it → `reefnet-deepcoastal`. Stop. **Result: `reefnet-deepcoastal`.**

Resolve **`model_version`** (device → site → global):

- Device card sets it → `"4.2.0"`. Stop. **Result: `"4.2.0"`.**

So for `RBX-7A2C`, both model fields come from the device card. The site card's `model_version: "4.1.0"` is *shadowed* by the device card and never used; the global `model_name`/`model_version` are likewise shadowed. The resulting manifest fragment (just the two fields we resolved here — the row also carries `site`, `source_png`, `sensor_variant`, `channel_scales`, and the three exception fields):

```json
{
  "device_id": "RBX-7A2C",
  "site": "site-pinnacle",
  "model_name": "reefnet-deepcoastal",
  "model_version": "4.2.0"
}
```

Now change the example so the device card is sparser, to show the per-field fallthrough. Suppose `devices/rbx-7a2c.yaml` is instead:

```yaml
# cards/devices/rbx-7a2c.yaml  (sparser variant)
model_version: "4.2.0"
# (no model_name)
```

Re-resolve:

- **`model_name`**: device card silent → fall to site card → site card silent → fall to global → `reefnet-coastal`. **Result: `reefnet-coastal`.**
- **`model_version`**: device card sets it → `"4.2.0"`. **Result: `"4.2.0"`.**

So now `model_name` comes from **global** (because neither device nor site set it) while `model_version` comes from the **device**. Two different fields, two different winning layers, for the *same* device. That's the whole point of resolving per-field. If you'd grabbed "the model block from the deepest card," you'd have ended up with no `model_name` at all (the device card didn't have one), or you'd have wrongly invented one.

One more permutation to cement the site layer actually doing something. Take a *different* fictional device, `RBX-22E9`, also at `site-pinnacle`, with **no device card at all**:

- **`model_name`**: device card absent → site card silent on `model_name` → global → `reefnet-coastal`.
- **`model_version`**: device card absent → site card sets `"4.1.0"` → **Result: `"4.1.0"`** (the site value, because there's no device card to override it).

Here the site card is the layer that wins `model_version`. Same global, same site, but because there's no device card, the site's `4.1.0` is the answer instead of being shadowed. That's device > site > global doing its job: the site beats global, and nothing beats the site because there's nothing more specific present.

### The three exception fields (don't deep-dive them here)

The remaining three manifest fields do **not** follow device > site > global. Each has its own rule, and each has its own section later in this notebook. I'm naming them here only so you don't accidentally sweep them into the default merge:

- **`confidence_threshold`** — resolved **site > global only; the device layer is ignored.** Device-level thresholds came out of a firmware path we don't trust, so even when a device card sets `confidence_threshold` (like the `0.55` in the example card above), you throw that device value away and resolve from site-then-global. The why and the full story are in **PM-4471**.
- **`input_size`** — also resolved **site > global only; device ignored.** Input size is a property of the per-site mount geometry (how far back the housing sits, what crop the optics give), not of the individual camera, and device cards were carrying stale sizes that no longer matched the deployed optics. Again: site overrides global, device value is discarded. Covered in **PM-4471** alongside the threshold pull-out.
- **`labels_version`** — resolved **from `global.yaml` for ordinary sites; site and device ignored.** (pilot sites are the one exception — there is one documented pilot-site exception, spelled out in the 2026-03-18 carve-out later in the label-governance memo). The label set is centrally governed and pinned across the whole fleet so that every device classifies against the same taxonomy; we deliberately do not let a site or a device drift to a different label version. Even if a site card or device card sets `labels_version`, you ignore it and take the global value. The governance rationale is in the **label-set governance memo**.

So the complete picture, field by field, for the manifest row:

- `model_name` → device > site > global
- `model_version` → device > site > global
- `confidence_threshold` → site > global (device ignored)
- `input_size` → site > global (device ignored)
- `labels_version` → global only for ordinary sites; site and device ignored (pilot sites — currently `site-alpha` — are the one exception and take it from the site card; see the label-governance memo)

Five settings, three different resolution rules. Two follow the default precedence; three are exceptions. If you remember nothing else from this section, remember that the "device always wins" instinct is correct for *exactly two* of the five fields, and is wrong — sometimes silently, sometimes by exactly the amount that quietly degrades the classifier — for the other three.

### Putting it next to the calibration half

To zoom back out for a second, because the card merge is only one input to a manifest row. A finished `devices[]` entry is built from two independent halves that meet at the device id:

- **From the PNG / calibration block:** `device_id`, `site` (decoded), `source_png` (the bare capture filename), `sensor_variant` (the bare letter), and `channel_scales` (the variant-mapped, nz-aware, 6dp-rounded RED/GREEN/NIR scales).
- **From the card merge described here:** `model_name`, `model_version`, `input_size`, `confidence_threshold`, `labels_version`.

The decoded `site` is the hinge: it's both a manifest field *and* the key you use to (a) check `allowed_sites` and (b) find the `sites/<site>.yaml` overlay. The decoded `dev` is the other hinge: it's the `device_id` *and* the key for `devices/<dev>.yaml`. Get the decode right and the cards practically address themselves; get the decode wrong (miscount the `co` bytes, say, and shift the dev/site offsets) and you'll be merging cards for the wrong device and wondering why the model names look scrambled.

### Things people actually get wrong (card edition)

A short list of the failures we've actually seen in code review and in shipped manifests, all card-merge related:

- **Treating the merge as a uniform deepest-wins overlay.** This is the big one. It produces correct `model_name`/`model_version` and *silently wrong* `confidence_threshold` and `input_size` (because it lets the untrusted/stale device values through) and sometimes a wrong `labels_version`. The merge is field-aware, not file-aware.
- **Pulling `labels_version` from the site or device because it happened to be set there.** Some site cards historically carried a `labels_version` line from before the central-pinning policy. Ignore it — for an ordinary site. `labels_version` is global for ordinary sites (pilot sites are the one exception — there is one documented pilot-site exception, spelled out in the 2026-03-18 carve-out later in the label-governance memo).
- **Confusing "no site card" with `unknown_site`.** The registry check is against `global.yaml`'s `allowed_sites`. Whether a `sites/<site>.yaml` file exists is irrelevant to that check. A recognized site with no card is normal (it just uses global defaults).
- **Reading the site from a card instead of the block.** The site is decoded from the binary. The card is *named* after the site; it doesn't *define* the site.
- **Case mismatches on filenames.** `RBX-7A2C` decoded → `devices/rbx-7a2c.yaml`. Match case-insensitively.
- **Filling in sparse cards from a template.** Sparse is correct. Missing means inherit. The layer you inherit from is per-field.

### War story: the manifest that looked perfect and wasn't

It's worth telling the story of how the "uniform overlay" bug actually bit us, because it's a *quiet* failure and quiet failures are the ones that survive review. Back when the merge was first written in jq, somebody — fine, it was me — reached for the obvious tool: take global, deep-merge the site card on top, deep-merge the device card on top of that, deepest layer wins. One expression, very tidy, very wrong. It produced a manifest that passed every sanity check we had at the time. `model_name` looked right. `model_version` looked right. The JSON was well-formed, the device count matched, scales were in range. We shipped it.

What we didn't notice for three weeks: a handful of devices had `confidence_threshold` values like `0.55` and `0.62` that had come straight off their device cards — values the firmware had written, that we already knew not to trust — and a couple of cameras at the deeper sites had `input_size: [512, 512]` lifted off a device card when the site geometry actually called for `[768, 768]`. The classifier didn't crash. It just got *worse*, unevenly, on exactly those devices, and we burned a week chasing it as a "model regression" before someone diffed the manifest against the cards by hand and saw that the device layer was leaking into fields it had no business touching.

The fix wasn't a smarter deep-merge. It was *abandoning* the single uniform merge and resolving each field with its own rule: device→site→global for the two model fields, site→global for `confidence_threshold` and `input_size`, and global-only for `labels_version`. Five fields, evaluated as what they are — three different policies — instead of one convenient lie. The lesson that stuck on the team: **a card merge is a per-field policy decision, not a file operation.** Any time you see a single generic "merge these three YAMLs, deepest wins," treat it as a bug until proven otherwise.

### How the merge tends to look in practice (jq/yq mechanics)

You don't need a specific implementation to follow the rules, but a sketch of how we actually express it helps avoid the uniform-merge trap. The shape that's worked for us is: convert the three YAML cards to JSON (yq does this), then resolve each manifest field with an explicit fallback expression rather than a blanket object merge.

For the two default-precedence fields, the pattern is "first non-null walking device → site → global." In jq-ish pseudocode, for a given device with its loaded `$device`, `$site`, and `$global` card objects:

```
model_name:    ($device.model_name    // $site.model_name    // $global.model_name)
model_version: ($device.model_version // $site.model_version // $global.model_version)
```

The `//` alternative operator does exactly the per-field fallthrough we want: it skips a layer that doesn't set the field (null/absent) and moves to the next. Because each field has its own little expression, a device card that sets `model_version` but not `model_name` resolves correctly — `model_version` stops at the device, `model_name` walks on down — without any special handling.

For the three exception fields, you deliberately *leave the device object out* of the expression (for `confidence_threshold` and `input_size`) or use *only* the global object (for `labels_version`):

```
confidence_threshold: ($site.confidence_threshold // $global.confidence_threshold)   # device omitted on purpose
input_size:           ($site.input_size           // $global.input_size)             # device omitted on purpose
labels_version:       ($global.labels_version)                                       # ordinary site: site & device omitted (a pilot site instead takes it from its site card — see the label memo)
```

The exact expressions for those three belong to their own sections — this is just to show the *shape*. The thing to internalize is that the device card object simply does not appear in the threshold or input-size resolution, and — for an ordinary site — neither site nor device appears in the labels resolution (a pilot site is the one exception; its label version comes from the site card, per the label-governance memo). You don't "merge then override" your way to that; you write it so the untrusted layer is never in the expression in the first place. That's much harder to get wrong than a blanket merge followed by surgical un-merging.

Two gotchas with the mechanics specifically:

- **`//` triggers on null *and* missing, which is what you want, but also on `false` and empty — be careful with boolean-ish fields.** None of our five card fields are booleans, so we're fine, but if you ever add one, `//` will treat `false` as "unset" and fall through. Use an explicit `has(...)` check for those.
- **YAML's loose typing on `model_version`.** Quote your versions in the cards (`"4.1.0"`, not `4.1.0`) or yq may hand you a number or a date-looking thing for something like `2.0`. The manifest wants the version as a string. We've had `model_version: 4.0` silently become the float `4` and then serialize as `"4"` in the manifest. Quote it in the card and the problem disappears.

### Quick precedence FAQ

A few questions that come up every onboarding, answered in field-voice so you don't have to re-derive them:

**Q: A device card and a site card both set `model_version`. Who wins?**
Device. `model_version` is a default-precedence field, and device beats site beats global. The site value is shadowed.

**Q: A device card and a site card both set `confidence_threshold`. Who wins?**
The *site*. `confidence_threshold` is an exception — site > global, device ignored — so the device value is discarded entirely and you resolve from the site card (then global if the site is silent). The device's threshold loses not because the site is "more specific" but because the device layer isn't in the running at all for that field.

**Q: A site card sets `labels_version` to something different from global. Now what?**
You ignore the site value and take global. `labels_version` is global-only. For an ordinary site there is no scenario where a site or device changes the labels version in the manifest; (pilot sites are the one exception — there is one documented pilot-site exception, spelled out in the 2026-03-18 carve-out later in the label-governance memo).

**Q: There's no device card for this device. Does it get quarantined?**
No. A missing device card just means no device-level overrides; you resolve from site and global. The only card-adjacent thing that quarantines a capture is the `allowed_sites` registry check (decoded site not on the list → `unknown_site`), and that has nothing to do with whether a YAML file exists.

**Q: The decoded site has no `sites/<site>.yaml`. Bad?**
No, as long as the site is in `allowed_sites`. No site card means the site uses global defaults for everything; that's a normal, recognized site that simply has no overrides.

**Q: `model_name` isn't set on the device or the site card. Where does it come from?**
Global. `global.yaml` is the floor for every field; both default-precedence fields ultimately fall through to it when nothing more specific sets them.

**Q: Should I deep-merge the cards and then fix up the exceptions afterward?**
No. Resolve per field with explicit expressions. The "merge then fix" approach is exactly how the leak in INC-territory above happened — it's too easy to forget one of the three exceptions and ship a manifest where the device layer quietly poisons a column.

That's the layer model and the default precedence. The next few sections are the postmortem and memo that *created* the three exceptions — read those before you wire up the threshold, input-size, and labels-version resolution, because each of them overrides the comfortable "device wins" habit in a different direction.
## PM-4471: bogus device thresholds, and the input_size pull-out

**Postmortem PM-4471** — opened 2025-09-12, signed off 2025-10-04. Authors: D. Okonkwo (inference), priya (field eng), and whoever was unlucky enough to be on the pager that week (it was me). Severity: we shipped two batches of garbage classifier runs before anyone noticed, so call it a 2. Could've been worse. Was nearly worse.

This is a long one. There are two findings braided together because we found them in the same week chasing the same smell, and if you only read half of this you'll re-introduce one of the bugs we're about to kill. So read the whole thing, or at least read the two **RULE** boxes and the closing checklist. The TL;DR if you're skimming on a boat: **device cards still win for `model_name` and `model_version`, but they DO NOT win for `confidence_threshold` and they DO NOT win for `input_size`. Both of those are site-driven now. Device value is ignored on both.** Everything below is why.

### How we noticed

Background, because new folks keep asking why the manifest merge has all these weird carve-outs. The inference settings that ride alongside each device in the downstream manifest don't come out of the camera. They come out of the YAML model cards. Three layers, lowest to highest:

1. `global.yaml` — the baseline. Everything has a value here, even if it's a boring one.
2. `sites/<site>.yaml` — per-site overrides. The site is whatever we decoded out of the calibration block's site field, not anything the operator typed into a clipboard.
3. `devices/<dev>.yaml` — per-device overrides. The dev id, again decoded, not typed.

For most of 2024 the merge rule was dead simple and we said it everywhere: **device beats site beats global.** Last writer up the stack wins. We even had it on the laminated cheat-sheet by the bench: "device > site > global, full stop." That cheat-sheet is now wrong in two places and this postmortem is the errata. Trust the errata, not the cheat-sheet.

The smell started in the weekly QA skim. Our coastal-shelf classifier had been running at what looked like a hair-trigger on a handful of cameras — way more detections than the same site's neighbors, a flood of low-quality boxes, the kind of output you get when somebody fat-fingers the confidence threshold down to nothing. priya pulled the per-capture inference logs for site-lagoon and site-pinnacle and the threshold field was all over the place. Some captures ran at 0.55 like they should. Some ran at 0.02. One ran at **1.7**, which is not a probability, which is not a number a threshold should ever be, which is the moment we knew something upstream was writing junk.

### Finding (a): the firmware wrote garbage thresholds into device cards

Here's the chain. The device cards (`devices/<dev>.yaml`) are not all hand-authored. A chunk of them get auto-populated by a little provisioning job that reads telemetry the camera firmware reports on first check-in, and stamps a starter device card. The idea was nice — a freshly-deployed ReefBox shows up, we already know its preferred exposure, its self-reported threshold hint, etc., and ops doesn't have to type it. The idea was nice. The firmware was not nice.

Firmware build `fw-2.3.1` (and, it turns out, the `2.3.0` RC that leaked onto a few field units before we caught it) had a bug in the routine that serializes the self-reported `confidence_threshold` hint. It was reading the value out of a fixed-point register and **forgetting to divide.** So a perfectly reasonable internal threshold of, say, 0.55 got reported as `55`, or after a different miscompute as `0.0`, or — my favorite — as a raw register value that, reinterpreted, came out `1.7`. The provisioning job dutifully wrote whatever number it got straight into the device card's `confidence_threshold:` line. No sanity clamp. Garbage in, garbage card, garbage inference.

Worked example. Device **RBX-7A2C** is deployed at **site-lagoon**. Here are the three relevant cards as they actually existed on 2025-09-12 (trimmed to the field in question):

```yaml
# global.yaml
confidence_threshold: 0.50
# ... lots of other keys ...
```

```yaml
# sites/site-lagoon.yaml
# lagoon water is turbid, we run a touch stricter to cut false positives
confidence_threshold: 0.62
```

```yaml
# devices/rbx-7a2c.yaml   <-- auto-stamped by provisioning from fw-2.3.1 telemetry
confidence_threshold: 1.7     # <- this is not a probability. this is a crime scene.
model_name: reefnet-coastal
model_version: "3.2"
```

Under the old "device > site > global" rule, the merge picked **1.7** for RBX-7A2C because the device layer is highest and it had a value. The classifier then treated 1.7 as the cut, which (depending on how the runtime clamps) either suppressed everything or, in the broken clamp path, behaved like 0 and let everything through. Either way: a whole camera's worth of useless captures, and nobody noticed for two QA cycles because the device card "looked" authoritative.

We pulled the blast radius. Across the fleet, **31 device cards** had a `confidence_threshold` outside `[0,1]`, and an unknown additional number had in-range but still-wrong values (a fixed-point miscompute can absolutely land you at a plausible-looking `0.31` that is nonetheless not what the device meant). That second category is the scary one: you can't filter it out with a range check because it's a *valid number that is lying to you.* That single observation is what killed the rule. We cannot trust ANY device-reported threshold, in-range or not, because the firmware path that produced them is fundamentally untrustworthy and we cannot distinguish a real device threshold from a miscomputed one after the fact.

We considered four fixes and I'll record why we rejected three of them, because somebody will propose them again next year:

- *"Clamp device thresholds to [0,1]."* Rejected. Clamping `1.7 -> 1.0` gives you a different wrong answer, and does nothing for the plausible-but-wrong `0.31` case.
- *"Re-derive the true threshold from the raw register."* Rejected. We don't always have the raw register in the manifest pipeline, the miscompute wasn't a single consistent transform across firmware revs, and we are not in the business of reverse-engineering our own firmware's arithmetic mistakes per-capture.
- *"Just fix the firmware and re-provision."* We DID fix the firmware (`fw-2.3.4`, divide restored, plus a clamp), but that doesn't retroactively fix the thousands of cards already stamped, and we can't block the manifest pipeline on a fleet-wide firmware rollout that takes a full survey season to land.
- *"Stop trusting the device layer for this one field."* Accepted. This is the only fix that's correct for both the out-of-range and the silently-plausible-wrong cases, requires no per-capture archaeology, and degrades gracefully — the site card is hand-tuned by people who know that site's water and optics, so it's a strictly better source than a firmware self-report anyway.

> **RULE (confidence_threshold precedence) — supersedes "device > site > global" for this field.**
> `confidence_threshold` resolves as **site > global ONLY.** The device card's `confidence_threshold` is IGNORED, always, whether or not it's present, whether or not it's in range, whether or not it looks reasonable. If the resolved site card has a `confidence_threshold`, use it; otherwise fall back to `global.yaml`. Device never participates. Reason: firmware bug (`fw-2.3.x`) wrote untrustworthy thresholds into auto-stamped device cards, and bad-but-plausible values are indistinguishable from good ones, so the whole device source is condemned for this field. See PM-4471(a).

So for RBX-7A2C above, the **correct** resolved threshold is `0.62` — the site-lagoon value. Not `1.7`. The device's `1.7` is discarded without a second look. If site-lagoon's card had *no* `confidence_threshold` line, RBX-7A2C would fall through to global's `0.50`. The device card's number is never in the running.

Note what this rule does NOT touch. RBX-7A2C's device card also carries `model_name: reefnet-coastal` and `model_version: "3.2"`. Those are real, hand-curated, and still authoritative. **The device card still wins for model_name and model_version.** We did not condemn the whole device layer — only its threshold. Keep that distinction sharp; it bites people.

### Finding (b): stale input_size that no longer matched the deployed optics

This one we found because we were already elbow-deep in the cards for finding (a), and D. Okonkwo noticed something else wrong while staring at the same files. Half the device cards carried an `input_size:` and a bunch of those values were *stale* — they described optics the camera no longer had.

Quick context on `input_size` for the new folks: it's the `[width, height]` the classifier resizes/letterboxes the capture to before inference. It is NOT a free choice. It's a function of the **physical mount geometry at the site** — the lens, the port window, the crop the housing imposes. Two cameras at the same site, even different hardware revisions, see the same framing because they're bolted into the same style of housing on the same style of mount. The input_size has to match the optics that are *physically deployed right now*, or the model gets a resized frame with the wrong aspect/crop and quietly loses accuracy. No crash. Just worse. The worst kind of bug.

Why were the device cards stale? Two reasons, both boring and both inevitable:

1. **Cameras get re-housed and re-deployed.** A ReefBox pulled from site-pinnacle (deep mount, narrow port) and redeployed to site-lagoon (shallow mount, wide port) has the same device id and the same auto-stamped or hand-edited device card — including a now-wrong `input_size` baked in from its *previous* posting. The device card travels with the device. The optics don't. The mismatch is structural.
2. **Optics upgrades happen per-site, not per-device.** When we swapped the port windows at site-pinnacle in mid-2025 (the anti-fouling coating refit), the correct input_size for every camera at that site changed *at once.* Updating one site card captured that. Hunting down N device cards to bump each one did not, and three of them never got bumped.

Worked example. Device **RBX-22E9**. It was originally provisioned at site-pinnacle, then physically pulled and redeployed to site-lagoon in 2025-08. Its decoded site field now reads `site-lagoon` (the calibration block is the source of truth for site, and the redeploy re-flashed calibration, so the block is correct). But its device card still carries the old pinnacle framing:

```yaml
# global.yaml
input_size: [512, 512]
```

```yaml
# sites/site-lagoon.yaml
# wide port, shallow mount -> wider frame
input_size: [768, 512]
```

```yaml
# sites/site-pinnacle.yaml   (for reference — RBX-22E9 is NOT here anymore)
input_size: [640, 640]
```

```yaml
# devices/rbx-22e9.yaml   <-- stale: this is the OLD pinnacle geometry
input_size: [640, 640]
model_name: reefnet-coastal
model_version: "4.0"
```

Under the old device-wins rule, RBX-22E9 would have been resized to `[640, 640]` — the geometry of a site it no longer lives at. The right answer is the site-lagoon value, `[768, 512]`, because that's the housing the camera is actually sitting in today. The device card's `[640, 640]` is a fossil. It describes optics that are, physically, somewhere else.

Same logic as finding (a), different field: the device layer is the wrong place to source this value, because the device card is a per-device artifact that does not (and structurally cannot) track per-site physical reality. The mount geometry belongs to the *site*. So the site card is the authority, the global is the fallback, and the device card sits this one out.

We checked, by the way, whether we could "just keep device cards in sync" — write a re-provision step on every redeploy that re-stamps input_size from the destination site. We rejected it for the same family of reasons as (a): it relies on every redeploy being recorded perfectly (they aren't — boats, weather, tired people), it doesn't fix the existing stale cards, and even when it works it's just laundering the site value through the device layer for no benefit. If the site is the source of truth, source from the site.

> **RULE (input_size precedence) — supersedes "device > site > global" for this field.**
> `input_size` resolves as **site > global ONLY.** The device card's `input_size` is IGNORED, always, present or not, plausible or not. Use the resolved site card's `input_size` if it has one; otherwise fall back to `global.yaml`. Device never participates. Reason: input_size is a function of per-site physical mount/optics geometry; device cards carry stale framing from prior deployments and don't track site optics upgrades. See PM-4471(b).

So RBX-22E9's correct `input_size` is `[768, 512]`. If site-lagoon had no `input_size`, it'd be global's `[512, 512]`. The device's `[640, 640]` is never considered.

### ERRATA-217 (2025-10-04): the cheat-sheet line is dead

For the record, because the laminated bench cheat-sheet still says it and somebody will photograph it and "fix" the pipeline back to wrong: the line **"model card precedence is device > site > global, full stop"** is SUPERSEDED as of PM-4471. It was never *fully* true after this; it's true for `model_name` and `model_version` and false for `confidence_threshold` and `input_size`. If you are reading the cheat-sheet and this notebook and they disagree, the later dated entry wins, and this is the later dated entry. Trust the errata, not the cheat-sheet. The reprint is on priya's desk waiting for the laminator.

A second thing the cheat-sheet implies and shouldn't: that "device card present" means "device value used." Not anymore, not for these two fields. Presence is irrelevant. We are not checking whether the device card *has* a `confidence_threshold` or an `input_size` before deciding to ignore it — we ignore it unconditionally. The merge doesn't branch on "does the device specify it." It branches on "which field is this," and for these two the device layer simply isn't in the lookup chain. Mentally: `confidence_threshold = site_card.confidence_threshold ?? global.confidence_threshold`, and `input_size = site_card.input_size ?? global.input_size`. The string `devices/<dev>.yaml` does not appear in either of those expressions. That's the whole behavior.

Addendum, 2026-03-18 (site re-optic). One carve-out to the `input_size` rule, and the only one: **site-bravo** was re-opticed this cycle back to the standard mount, but its **site card was never updated** — it still lists the *old* `input_size`, which is now wrong for the deployed hardware. Until that card is fixed, **`input_size` for site-bravo comes from `global.yaml`, not from the site card** — the site card's `input_size` line is stale and must be ignored, exactly like the dead `labels_version` line in the earlier trap. This applies to site-bravo only; every other site still resolves `input_size` as site > global per the rule above, and the device layer is still never consulted for anyone. Per the reading convention, this later note governs for site-bravo where it conflicts with "site > global, always" above.

### War story: the day we almost "fixed" it wrong

Worth recording because it nearly cost us another bad batch. Two weeks after we shipped the merge rewrite, a well-meaning contractor saw site-pinnacle running every camera at `[640, 640]` (the correct pinnacle geometry) and noticed that one device's card *also* said `[640, 640]`, and concluded "see, the device card was right all along, this carve-out is pointless, let's simplify it back to device-wins." He opened a PR. He was, in that one instance, accidentally correct — that device happened to have a card matching its current site. That's the trap. **A stopped clock matches twice a day.** The device card matching the site value on one camera does not make the device card a trustworthy source; it makes it a coincidence. The very next camera he'd have hit was RBX-22E9 with its fossil `[640, 640]` at a `[768, 512]` site. We closed the PR with a link to this postmortem and a note: the rule is not "use the device value when it looks right," because *we cannot tell when it looks right.* The rule is "don't use the device value." Binary. No judgment call at merge time. That's the only version that's safe, because the entire failure mode of both findings is values that look fine and aren't.

Same energy applies to threshold. Do not write a heuristic like "use the device threshold if it's in [0,1], else fall back to site." That reintroduces exactly the silently-plausible-wrong case from finding (a) — a miscomputed `0.31` is in range and still wrong. The device threshold is out. Not range-checked. Out.

### Edge cases we had to nail down during the merge rewrite

- **Device card present but the field is the only key in it.** Doesn't matter. A `devices/rbx-xxxx.yaml` containing nothing but `confidence_threshold: 0.4` contributes *nothing* to the resolved threshold. The file can still legitimately carry `model_name`/`model_version`; those are read, the threshold is not.
- **Site card missing the field entirely.** Then you fall through to global for that field. Device is STILL not consulted. e.g. if `sites/site-lagoon.yaml` had no `input_size`, RBX-22E9 resolves to global's `[512, 512]`, NOT the device's `[640, 640]`. The fallback ladder for these two fields has exactly two rungs: site, then global. There is no third rung.
- **Both site and global missing the field.** Then the value is genuinely absent and that's a manifest/schema problem to raise loudly — but the resolution still never reaches for the device card to paper over it. If global is missing a baseline `input_size` or `confidence_threshold`, fix global. Don't let the device sneak back in as an emergency source.
- **Device at an unknown site.** If the decoded site isn't in `global.yaml`'s `allowed_sites`, the capture is quarantined `unknown_site` long before we ever get to model-card merging, so the question is moot — but note the merge order: site resolution depends on a *recognized* site, and quarantine handling runs first. You won't be merging cards for a capture that's already quarantined.
- **`model_name`/`model_version` genuinely absent from the device card.** Then those fall through device -> site -> global like always. The carve-outs are field-specific; don't let the threshold/input_size rule leak over and make you start ignoring device model fields. Device still wins those when present.

### The thing that makes this confusing, stated plainly

We now have a model card precedence that is NOT uniform across fields. I know that's annoying. I know "device > site > global, full stop" was easier to remember. But "easier to remember" gave us 1.7-threshold cameras and 640-square frames on wide-port mounts, so here we are. The honest mental model:

- **`model_name`** — **device > site > global.** Device wins if present. (Unchanged. Device cards are the right place for which model a specific camera runs.)
- **`model_version`** — **device > site > global.** Device wins if present. (Unchanged.)
- **`confidence_threshold`** — **site > global ONLY.** Device IGNORED. (PM-4471a — firmware wrote garbage.)
- **`input_size`** — **site > global ONLY.** Device IGNORED. (PM-4471b — stale per-site optics geometry.)

And while we're listing the carve-outs so nobody thinks these two are the only special cases — there's also `labels_version`, which is its own animal: it's centrally pinned and (as of this postmortem) comes from **global**, because we will not have two cameras disagreeing about what label index 7 means. That one isn't part of this postmortem and isn't mine to settle — the **label-set governance memo** is the authority on it, so treat that memo's version of the rule as current — but it lives in the same family of "the default precedence does not apply here," so I'm naming it so you don't trip on it and think we forgot a layer.

The unifying principle, if you want one sentence: **a device card is authoritative about the device's identity (what model it runs), but NOT about anything that is really a property of the site or that the firmware lied about.** Threshold was a lie; input_size is a site property the device card can't keep current. Both get pulled out of the device's hands.

### What actually changed in the pipeline

- The manifest merge step was rewritten so that the resolved value for `confidence_threshold` and `input_size` is computed from **only** the site and global layers. We don't even read those two keys out of the device card anymore — not to compare, not to log, nothing. They're dead to the merge. (We briefly logged a warning when a device card's threshold/input_size disagreed with the resolved value, then turned it off because *every single device with fw-2.3.x tripped it* and it drowned the logs. The disagreement is expected now; it is not news.)
- Firmware `fw-2.3.4` shipped with the divide restored and an output clamp on the threshold hint. This does not change the rule. **Even on fixed firmware, the device threshold is still ignored** — we are not re-litigating per-firmware-version trust, the field is just site > global and that's the end of it. Same for input_size: fixing provisioning to re-stamp on redeploy would be nice hygiene but changes nothing about the rule.
- Backfill: we did NOT mass-edit the stale device cards. They're still sitting there with `1.7` and `[640, 640]` and whatever else. That's fine. The pipeline ignores those fields. Editing them would be busywork that creates merge churn and tempts someone to "trust" them again. Leave the fossils in the rock.

### Re-derived example, end to end (so the rules are unambiguous)

Take **RBX-7A2C** at **site-lagoon** with the cards shown earlier, and assume it decodes clean (good CRC, variant A or B — doesn't matter for this part, the model card merge is independent of the calibration scale math). Its manifest entry's settings resolve like so:

- `model_name`: device says `reefnet-coastal`, present, device wins -> **`reefnet-coastal`**.
- `model_version`: device says `"3.2"`, present, device wins -> **`"3.2"`**.
- `confidence_threshold`: device says `1.7` -> **IGNORED.** Site-lagoon says `0.62` -> **`0.62`**.
- `input_size`: (say RBX-7A2C's device card has no input_size at all) -> device IGNORED regardless. Site-lagoon says `[768, 512]` -> **`[768, 512]`**.
- `labels_version`: global only -> whatever `global.yaml` pins. Site/device ignored.

And **RBX-22E9** at **site-lagoon** (the redeployed one):

- `model_name`: device `reefnet-coastal` -> **`reefnet-coastal`**.
- `model_version`: device `"4.0"` -> **`"4.0"`** (yes, two devices at the same site can run different model versions — that's exactly why device wins for model fields).
- `confidence_threshold`: device card here has none; doesn't matter, device ignored anyway -> site-lagoon `0.62` -> **`0.62`**.
- `input_size`: device `[640, 640]` (stale pinnacle geometry) -> **IGNORED.** Site-lagoon `[768, 512]` -> **`[768, 512]`**.

Notice RBX-22E9 ends up with the *correct lagoon framing* `[768, 512]` even though its own card screams `[640, 640]`, and the *correct lagoon threshold* `0.62` even though somewhere on the fleet a sibling device's card screams `1.7`. That's the whole point. The site is the adult in the room for geometry and threshold.

### Checklist for anyone touching the merge

1. Resolving `model_name` or `model_version`? Use **device > site > global.** Device wins if present. Unchanged.
2. Resolving `confidence_threshold`? Use **site > global.** Do not read the device card's value. At all.
3. Resolving `input_size`? Use **site > global.** Do not read the device card's value. At all.
4. Resolving `labels_version`? Not this postmortem's field — it's centrally pinned and governed separately. Follow the **label-set governance memo** for its authoritative, current rule rather than assuming the default ladder here.
5. If you ever feel the urge to "just trust the device card, it's probably right" for threshold or input_size — re-read finding (a) and finding (b). It is not probably right. That instinct is what PM-4471 is about.

Closed 2025-10-04. Action items: pipeline merge rewrite (done), `fw-2.3.4` rollout (in progress, tracked separately), cheat-sheet reprint with the two carve-outs (priya owes us this, the laminator is broken again). — D.O. / priya / pager-victim
## Label-set governance memo

**FROM:** Priya (label ops / model governance)
**TO:** everyone who touches the manifest builder, anyone wiring up a new site, and whoever inherits this notebook after I rotate off
**RE:** `labels_version` is centrally pinned. Stop trying to override it. This is the third precedence exception and it is the one people keep getting wrong.
**Filed under:** governance, INC-0418 follow-up, please-read-before-you-edit-yaml

---

Okay. This is a memo, not a war story, so I'll keep the prose tighter than the incident reports earlier in this notebook, but I need it written down somewhere permanent because we have now had the **same** conversation in three different standups and I am tired of being the institutional memory for it.

Short version, so the people who skim get the load-bearing sentence: **the label set is governed centrally. for an ordinary site, `labels_version` comes from `global.yaml` — site and device files get no vote, there is no precedence ladder, just the one global source. The single exception is a pilot site (there is one documented pilot-site exception, spelled out in the 2026-03-18 carve-out later in the label-governance memo).**

If you only remember one thing from this section, remember that. The rest of the memo is me explaining *why*, showing you the *failure modes* we already hit, and giving you a couple of worked examples so you can sanity-check your own builder output.

### Where this sits relative to the other precedence rules

Most of the inference settings in this system follow the boring, intuitive rule: more specific wins. A device card overrides a site card, a site card overrides the global baseline. That "device > site > global" ladder is the **default**. But — and the rest of the notebook hammers this elsewhere — the default does NOT apply to everything. There are precedence *exceptions*, and I am the keeper of the third one.

To be explicit, because new folks always conflate them, here are the three exceptions as they actually behave, side by side:

- **`input_size`** — this is NOT device > site > global. Input size is a function of the *mount geometry* at a physical site (the housing, the port glass, the crop the optics force on us). A device can't know better than the site about the geometry it's bolted into. So the rule is **site > global only**, and the device card is ignored for this field. If a device card sets `input_size`, it is noise — drop it on the floor.
- **`confidence_threshold`** — also NOT the default ladder. There's a firmware bug (documented earlier; I won't re-litigate it here) that means device-reported thresholds are untrustworthy. So this one is **site > global only** as well, device ignored. Same shape as input_size: device is silently disregarded.
- **`labels_version`** — MINE. This is the strict one. For an ordinary site it is **global**. Not site > global. Not device > site > global. Just global — site ignored, device ignored. Even if an ordinary site card screams `labels_version: v9` in 72pt font, the manifest gets whatever `global.yaml` says. *(pilot sites are the one exception — there is one documented pilot-site exception, spelled out in the 2026-03-18 carve-out later in the label-governance memo.)*

So the full mental model, if you want the cheat version: `model_name` and `model_version` use the normal ladder (device > site > global). `input_size` and `confidence_threshold` are site > global (device dropped). And `labels_version` is global-only (site AND device both dropped). Three settings, three different rules, and `labels_version` is the most locked-down of the lot.

The thing I want to drill in: `labels_version` is not "more global-leaning" than the others. It is *categorically* global for every ordinary site (pilot sites are the one exception — there is one documented pilot-site exception, spelled out in the 2026-03-18 carve-out later in the label-governance memo). The other two exceptions still let a more-specific tier (the site) win. Label version does not even give the site that courtesy.

### Why we pin it centrally (the rationale, so nobody "fixes" this later)

The label set is the dictionary the offline classifier uses to turn class indices into meaning. Index 14 means one thing under `labels-2024.09` and potentially a completely different thing under `labels-2025.02` if we re-ordered or inserted a class. The model weights, the scoring code, and the label dictionary are a **matched set**. You cannot mix and match them per-camera and expect coherent output.

Here is the failure we are protecting against, stated plainly: if Camera A in `site-lagoon` is allowed to run `labels-2025.02` while Camera B fifty meters away in the same survey is allowed to run `labels-2024.09`, then two detections that came out of the *same dive* are no longer comparable. The "fish" class might be index 7 in one and index 11 in the other. Downstream aggregation silently lies. Nobody notices for weeks because the JSON still validates and the numbers still look like numbers. Then someone builds a population trend chart across the whole reef and it is garbage, and we spend a sprint figuring out that the label dictionary drifted per-device.

That is exactly what INC-0418 was. I'll get to it.

So governance pins it. There is one canonical `labels_version` for the entire fleet at any given time, it is declared in `global.yaml`, and it changes only when *I* (or whoever holds this hat) bump it deliberately, after we have validated that every active model card is compatible with the new dictionary. Centralized, auditable, one knob. That is the entire point. The moment you let it be overridable per-site or per-device, you have re-created the drift problem we built the governance for.

### The YAML, concretely

Here's roughly what the relevant slice of `global.yaml` looks like. Fictional values, obviously — do not copy these into prod:

```yaml
# global.yaml  (baseline model card + the site registry)
manifest_defaults:
  model_name: reefnet-coastal
  model_version: 3.2.0
  input_size: [640, 640]
  confidence_threshold: 0.35
  labels_version: labels-2025.02   # <-- CENTRALLY PINNED. this is the only one that counts.

allowed_sites:
  - site-lagoon
  - site-pinnacle
  - site-shelf
  - site-22e9-north
```

(Yes, `allowed_sites` lives here too — that's the site registry the quarantine logic uses for `unknown_site`. Different concern, same file. Don't confuse the two; a site being in `allowed_sites` has nothing to do with whether that site can set `labels_version`. It can't, regardless.)

Now a **site** card. Say `sites/site-lagoon.yaml`:

```yaml
# sites/site-lagoon.yaml
model_version: 3.3.1          # legit: model_version uses the normal ladder, site can win over global
input_size: [512, 512]        # legit: input_size is site > global, this WILL be used
confidence_threshold: 0.42    # legit: confidence_threshold is site > global, this WILL be used
labels_version: labels-2025.06   # <-- IGNORED. has no effect. should not be here. delete it.
```

That last line is the trap. It *looks* authoritative. It is sitting in a site card that legitimately overrides three other fields. A reasonable person reading this file assumes all four lines do something. **Three of them do; the fourth is dead** — for an ordinary site. The manifest for any device at `site-lagoon` gets `labels_version: labels-2025.02` (from global). **There is exactly one exception to this, added later for the pilot program (the 2026-03-18 addendum a few paragraphs down); it is the sole case where a site's `labels_version` is honored. `site-lagoon` is not a pilot site, so the rule here holds as written — but do not generalize "the site line is always dead" without reading that addendum.**

And a **device** card, `devices/RBX-7A2C.yaml`:

```yaml
# devices/RBX-7A2C.yaml
model_name: reefnet-coastal-xl   # legit: model_name uses the normal ladder, device can win
labels_version: labels-2024.09   # <-- IGNORED. device gets no vote here either.
```

Device sets `model_name` — fine, that's the default ladder, device wins for that field. Device *also* sets `labels_version` — completely inert. The manifest still gets `labels-2025.02` from global. The device card might as well not have that line. (It also tries nothing on `input_size`/`confidence_threshold`, which is correct because those ignore the device too — but `labels_version` is the field where BOTH the more-specific tiers are mute.)

Addendum, 2026-03-18 (pilot program). Everything above is the steady-state rule and still holds for every ordinary site. When we stood up the early-access **pilot** program we carved out exactly one wrinkle, and this is the only place the global-only label pin ever bends: a **pilot site runs its own label set ahead of the central pin**, so for a device whose decoded `site` is a pilot site, `labels_version` is taken from that **site** card after all — not from global. Right now the pilot roster has a single entry, **`site-alpha`**. So: a device at `site-alpha` takes `labels_version` from `sites/site-alpha.yaml`; a device at any other site still takes it from global as described above. Nothing else about the label rule changes, and no other field is affected. (Per the reading convention, this later note governs where it conflicts with the "global only, full stop" wording earlier in this memo.)

### Worked resolution example

Let me walk one device all the way through, because seeing the four governed fields resolve next to each other is the fastest way to internalize the asymmetry.

Device `RBX-7A2C`, decoded site comes out as `site-lagoon`. Using the three files above:

- **`model_name`** → default ladder, device > site > global. Device card sets `reefnet-coastal-xl`. Site card doesn't set it. Global has `reefnet-coastal`. **Device wins → `reefnet-coastal-xl`.**
- **`model_version`** → default ladder, device > site > global. Device doesn't set it. Site sets `3.3.1`. Global has `3.2.0`. **Site wins (no device override) → `3.3.1`.**
- **`input_size`** → exception: site > global, device ignored. Site sets `[512, 512]`. Global has `[640, 640]`. **Site wins → `[512, 512]`.** (No device value exists, but it wouldn't matter if it did.)
- **`confidence_threshold`** → exception: site > global, device ignored. Site sets `0.42`. Global has `0.35`. **Site wins → `0.42`.**
- **`labels_version`** → global-only for an ordinary (non-pilot) site like this one. Device says `labels-2024.09`. Site says `labels-2025.06`. **Both ignored — `site-lagoon` is not on the pilot roster. Global wins → `labels-2025.02`.** (A device at a *pilot* site would instead take its site card's `labels_version`; see the pilot addendum above. This example is a non-pilot site, so global wins.)

Notice the pattern in the last three lines: as you go down the list the source gets *more* locked down. `input_size` and `confidence_threshold` still let the site speak. `labels_version` lets *no one* speak except global. The resulting manifest fragment (just the governed bits) for this device:

```json
{
  "device_id": "RBX-7A2C",
  "site": "site-lagoon",
  "model_name": "reefnet-coastal-xl",
  "model_version": "3.3.1",
  "input_size": [512, 512],
  "confidence_threshold": 0.42,
  "labels_version": "labels-2025.02"
}
```

If your builder emits anything other than `labels-2025.02` for that field given those inputs, your builder has a bug. That's a clean unit test, honestly — wire it up.

### INC-0418, briefly (the reason this memo exists)

I promised the story, here's the compressed version. Last quarter someone — well-meaning — was prepping a new model rollout and staged the next label dictionary by dropping `labels_version: labels-2025.06` into a couple of site cards as a "soft launch," figuring they'd flip global once it was validated. Their mental model was the default ladder: "site overrides global, so I'll override at the site level for the pilot sites and leave everyone else on the old one."

The intent was reasonable. The model of how `labels_version` resolves was wrong. *Had* the builder honored site-level label versions, half the fleet would have been decoding detections against `labels-2025.06` while the other half used the global pin, and we'd have had exactly the silent index-drift catastrophe described above — split across a single survey window.

We got lucky: the builder (correctly, per this rule) ignored the site-level `labels_version` entirely, so production stayed on the global pin and nothing actually broke in the output. But it took us most of a day to figure out *why* the "soft launch" wasn't taking effect, because the person who staged it was staring at YAML that said `labels-2025.06` and could not understand why the manifest kept saying the old version. The answer: working as designed. The field is global-only. The site lines were inert the whole time.

Two lessons came out of 0418, and they're now policy:

1. **You do not soft-launch a label set per-site — not ad hoc.** The one and only sanctioned way a site-level `labels_version` ever takes effect is the governed **pilot-site** carve-out added later (the 2026-03-18 addendum earlier in this memo). Outside that single roster, a `labels_version` sitting in a site card is inert and the builder throws it away. So: if you want a subset of cameras on a new dictionary and they are *not* pilot sites, that is a real model-card split (new `model_name`/`model_version` that bundles the right labels), governed and reviewed — not a sneaky `labels_version` override.
2. **A label-set bump is a single, deliberate edit to `global.yaml`,** done by governance, after compatibility validation, and it flips the entire fleet at once. That is a feature. Atomic, auditable, no drift. If that scares you, good — it should, and that's why one person owns the knob.

### ERRATA-031 (2026-02-11)

Cleaning up a decoy I tripped over while writing this. There is an **early** onboarding note buried somewhere up in the front third of this notebook — I think it's in the "first week setup" jottings — that lists the precedence rules and says something to the effect of *"all model-card fields resolve device > site > global; just remember input_size and confidence_threshold ignore the device."* It enumerates two exceptions and stops there.

**That note is wrong, or at least dangerously incomplete, and per our reading convention the later entry wins — so this ERRATA supersedes it.** There are **three** exceptions, not two. `labels_version` is the third, and it is stricter than the other two: it ignores the device *and* the site, sourcing only from global. If you onboarded off that early note and built a mental model with two exceptions, patch it now. Trust the errata, not the cheat-sheet.

I suspect the old note predates the central-governance decision — back in the very early days we may genuinely have let label version ride the normal ladder, before INC-0418's ancestor incidents convinced us to lock it down. Doesn't matter. Current rule, the one the builder implements and the one you are bound by: **`labels_version` is global-only — with the single pilot-site carve-out recorded in the 2026-03-18 addendum earlier in this memo.** That addendum is dated after this ERRATA, so per the reading convention it governs for pilot sites: a device on the pilot roster (currently just `site-alpha`) takes `labels_version` from its site card; every other device takes it from global, exactly as this ERRATA says.

### How to bump the label set (the governed procedure)

Since the whole memo is "don't override it locally," I owe you the actual sanctioned way to change it, so nobody feels they have to smuggle a new version in through a site card. Here is the runbook. It is deliberately heavyweight; the friction is the feature.

1. **Propose.** Open a governance ticket describing the new dictionary, what changed (added classes, re-ordered classes, renamed classes), and which model cards it's meant to pair with. Re-ordering or removing a class is the dangerous case — that's where the index-drift bites — so call it out loudly. Pure appends (new classes tacked on the end, old indices untouched) are lower risk but still go through the process.
2. **Validate compatibility.** For every active `model_name`/`model_version` currently referenced anywhere in the site and device cards, confirm the candidate dictionary is the one those weights were trained/scored against. If a model card is incompatible with the new labels, it has to be retired or rev'd *first*. We do not ship a global label bump that strands a live model on a mismatched dictionary.
3. **Stage in a non-prod manifest build.** Build the manifest with the candidate `labels_version` pinned in a *copy* of `global.yaml`, diff the output against prod. The only field that should change is `labels_version`, and it should change uniformly across every **non-pilot** device — they all flip together. Pilot-site devices are the deliberate exception: they track their own site card's label version, so a global bump does *not* move them, and their `labels_version` will differ from the fleet. So "different labels on the pilot roster, identical labels everywhere else" is correct; the only thing that signals a builder bug is a *non-pilot* device whose label diverges from global.
4. **Flip global, once.** Edit `global.yaml`'s `labels_version` to the new value. One line. One commit. Reviewed by governance.
5. **Rebuild and publish.** The next manifest build carries the new version fleet-wide, atomically.

Note what is conspicuously absent from that list: there is no step where you edit a `sites/*.yaml` or a `devices/*.yaml` to change the label version. There never is. The runbook touches `global.yaml` and nothing else, because that is the only file that sources this field.

A worked example of a clean bump. Suppose we're moving the fleet from `labels-2025.02` to `labels-2025.08`. Before:

```yaml
# global.yaml (before)
manifest_defaults:
  labels_version: labels-2025.02
```

After the single governed edit:

```yaml
# global.yaml (after)
manifest_defaults:
  labels_version: labels-2025.08
```

That's the whole change. Every device in the rebuilt manifest — `RBX-7A2C`, `RBX-22E9`, all of them, across `site-lagoon`, `site-pinnacle`, `site-shelf`, wherever — now reports `labels-2025.08`. No site card touched. No device card touched. If `site-pinnacle.yaml` still has a stale `labels_version: labels-2024.09` line in it from some forgotten experiment, the rebuilt manifest *still* shows `labels-2025.08` for every Pinnacle device, because that stale line was never being read in the first place. (Go delete it anyway. Stale inert config is how the next INC-0418 gets seeded.)

### Auditing the manifest after a build

Because this field is fleet-uniform, it's the easiest one in the whole manifest to audit, and you should. After any build — routine or post-bump — run the dead-simple invariant: **collapse the `labels_version` of every **non-pilot** device in the `devices` array; you must get exactly one distinct value, equal to the `labels_version` pinned in `global.yaml`. Pilot-site devices are the deliberate exception and carry their own site card's value.**

If you're poking at the manifest JSON by hand, that's a one-liner: pull `labels_version` out of each device object, dedup, and assert the set has size one. More than one distinct label version in a single manifest is a red flag full stop — it means either the builder is honoring a site/device override (a bug, given this rule) or someone hand-edited the output (don't). Either way, stop and investigate before that manifest feeds the classifier.

The same check is your regression test for the builder itself: feed it a `global.yaml` pinning some value, plus site and device cards that *deliberately* set conflicting `labels_version` values (this is a great place to use an obviously-fake decoy like `labels-9999.99` so a leak is glaring), build, and assert every device comes out with the global value and the decoys appear nowhere. If a decoy shows up in the output, the precedence handling for this field is broken. I cannot stress enough how cheap this test is to write and how expensive the bug is to catch in the wild.

One more auditing note, so nobody panics: it's completely normal and expected to see *different* `model_name`, `model_version`, `input_size`, and `confidence_threshold` values across devices in the same manifest — those fields legitimately vary by their own rules (the ladder, or site > global). Variation there is fine. Variation in `labels_version` is never fine. That's the asymmetry you're auditing for. Uniform label version, possibly-varied everything-else.

### Quick FAQ, because I will be asked these anyway

**Q: My site card sets `labels_version`. Will it be used?**
No. Never. Delete the line so the next person doesn't get confused, but functionally it does nothing today.

**Q: What if `global.yaml` doesn't specify `labels_version`?**
Then governance has dropped the ball and you should page me, because the global card is *required* to pin it. There is no site/device fallback to rescue you — that's the whole point. Empty global label version is a governance failure, not something the builder papers over by reaching down to a site card. It won't reach down. Fix global.

**Q: Two devices in the same site need different label sets.**
They don't. If you think they do, what you actually have is two different *models*, and that's `model_name`/`model_version` territory (which legitimately can differ per device via the normal ladder, with each model bundling its compatible labels). The label *version* field stays global. Come talk to me and we'll model it properly.

**Q: Does any of this interact with quarantine?**
No. Quarantine (`missing_calibration`, `bad_checksum`, `sensor_variant_c`, `unknown_site`, `superseded`) is decided long before we ever resolve model-card fields. A capture that survives quarantine and makes it into the `devices` array gets its `labels_version` from global like every other non-pilot device (pilot-site devices take theirs from the site card). A quarantined capture never gets model-card fields at all. Separate stages, don't cross the wires.

**Q: I'm writing the manifest builder. What's the one-liner?**
For `labels_version`: for a non-pilot site, read `global.yaml`'s pinned value and write it — do not look at the site or device card. For a pilot site (currently just `site-alpha`; see the label memo's 2026-03-18 carve-out), read `labels_version` from the site card instead. That single branch is the only precedence this field needs.

---

That's the memo. Three precedence exceptions: `input_size` (site > global, device ignored), `confidence_threshold` (site > global, device ignored), and `labels_version` (**global for ordinary sites, site-supplied for pilot sites — see the label memo carve-out — device always ignored**). The label version is the strictest of the three for ordinary sites on purpose, it's centrally governed on purpose, and it bites people on purpose-adjacent-to-accident roughly once a quarter. Now it's written down. Point newcomers here.

— Priya
## INC-2259 and the duplicate-capture dedup policy

**INC-2259** — opened 2025-07-18, closed 2025-08-06. On-call: me (it's always me). Field eng: priya. Secondary: J. Reyes, who actually found the bug and is therefore the only person who comes out of this looking good. Severity 3, because nothing crashed and nothing went to a customer — but it's the kind of 3 that's secretly a 2, because for about six weeks our manifest was quietly carrying the *wrong calibration* for a handful of cameras and producing perfectly valid-looking inference against stale numbers. No alarms. Just wrong. The worst kind, again.

This section is the writeup *and* the policy. If you only take one thing away: **when the same device shows up in more than one capture, you keep the capture with the highest `seq`, and every other same-device capture is quarantined `superseded`.** Not the first one. Not the alphabetically-first filename. Not the newest file mtime. The highest decoded `seq`. There's a wrong rule we shipped first, documented below so you recognize it and kill it on sight — but the box that matters is the **RULE** box near the end. Trust the errata, not the original script.

### Why a device shows up more than once at all

New folks reasonably ask: why would we ever have two captures of the same camera in one batch? Aren't device ids unique? The device id is unique to the *camera*. It is not unique to the *capture*. A capture is one PNG, taken at one moment, carrying one calibration block. The same physical camera produces many captures over its life, and our intake batch is "every PNG that landed in the staging bucket since the last run," not "one PNG per camera." So duplicates are normal and expected. The usual ways we end up with several captures of one `dev` in a single batch:

- **Redeploys.** A ReefBox gets pulled for cleaning, re-housed, dropped back on the mount, and re-flashed. Each redeploy re-writes the calibration block (new white balance bench, possibly a new site, definitely a bumped `seq`) and produces a fresh capture PNG. If two redeploys of the same unit land in the same intake window — which happens constantly during a refit week — that's two captures, same `dev`, different `seq`.
- **Re-benches without a pull.** Sometimes we re-run the white-balance/black-level bench on a deployed camera in place (diver swaps a calibration target in front of the port, firmware re-derives, writes a new block, snaps a calibration capture). New block, new `seq`, same `dev`, no physical move. Another duplicate.
- **Re-uploads / replays.** A boat with flaky uplink re-sends a batch it already sent. Or someone replays last week's staging dump into this week's run "just to be safe." Now you've got the *same* capture twice, or last week's capture sitting next to this week's. Same `dev`, and the `seq` tells you which is which.
- **Plain operator do-overs.** First capture looked smudged, diver wiped the port and took another. Two captures, minutes apart, same `dev`, consecutive `seq`s.

In every one of those cases the calibration block is the authority on which capture is *current*, and the field inside the block that encodes recency is `seq`.

### Reminder: what `seq` is

`seq` is the uint16 at **bytes 4-5** of the decoded calibration block (big-endian, like every multi-byte integer in this format). It's a monotonic capture/calibration counter the firmware bumps every time it writes a new block for that device. Higher `seq` = later write = more current calibration. That's its entire job, and it's exactly the thing we need for dedup. We are *not* reading the seq off the filename, and we are *not* inferring recency from the file's modification time on disk (mtime is a property of when the file was copied around, which has nothing to do with when the camera wrote the block — a re-upload of an old capture can have a brand-new mtime). The recency signal lives **inside the decoded binary**, in those two bytes, and nowhere else.

A subtle point that bites people: `seq` is only meaningful **per device.** Comparing the `seq` of RBX-22E9 against the `seq` of some unrelated camera RBX-7A2C tells you nothing — they're separate counters. Dedup is always "group by `dev`, then compare `seq` *within* the group." Two different devices that happen to share a `seq` value are not duplicates of anything; they're just two devices. Don't cross the streams.

### How we noticed — the actual incident

J. Reyes was spot-checking the post-refit manifest for site-lagoon in mid-July and noticed that **RBX-22E9** had channel scales that didn't match the bench sheet from its most recent re-bench. The bench sheet said one set of white-balance numbers; the manifest row showed an older, slightly-off set. Not wildly off — close enough that the inference output looked fine at a glance, which is exactly why it had survived QA for weeks. But wrong.

We pulled the intake for that batch. RBX-22E9 appeared in **three** captures:

| source_png            | decoded dev | decoded seq |
|-----------------------|-------------|-------------|
| `rbx-22e9-0004.png`   | RBX-22E9    | 4           |
| `rbx-22e9-0009.png`   | RBX-22E9    | 9           |
| `rbx-22e9-0002.png`   | RBX-22E9    | 2           |

Three redeploys/re-benches of the same unit, all caught in one intake window during the refit. The *correct* capture to carry forward is `seq=9` — the latest calibration the camera ever wrote. That's the one whose block matched Reyes's bench sheet. But the manifest had picked **`rbx-22e9-0002.png`** (`seq=2`), the *oldest* of the three. Which made no sense as "latest"... until we read the dedup script.

### The decoy: "keep the first file alphabetically" (THIS IS WRONG)

Here is the original dedup logic, lifted verbatim in spirit from the first manifest builder (circa early 2025). When a device appeared more than once, it did this:

```sh
# WRONG. Do not resurrect this. Kept here as a tombstone.
# group captures by decoded dev; within each group, sort the
# capture FILENAMES and keep the first one.
for dev in $(decoded_devs | sort -u); do
  winner=$(captures_for "$dev" | sort | head -n1)   # <-- first filename, alphabetical
  emit "$winner"
  # (older versions didn't even quarantine the rest — they just vanished)
done
```

Whoever wrote it (it was me, I'm not going to pretend otherwise) reasoned: "if there are duplicates, just deterministically pick one so the manifest is stable run-to-run. Sort the filenames, take the first. Done." It *is* deterministic. It is also completely disconnected from which capture is actually current.

Watch it fail on RBX-22E9. The three filenames are `rbx-22e9-0002.png`, `rbx-22e9-0004.png`, `rbx-22e9-0009.png`. Sort those as strings and the first is **`rbx-22e9-0002.png`** — which carries `seq=2`, the *oldest* calibration. The script confidently picked the stalest possible capture and threw away the `seq=9` one that we actually wanted. And in the early version it didn't even quarantine the discarded two; they just silently evaporated, so there was no trail saying "we dropped seq 9 and seq 4." We only reconstructed it by re-decoding the raw intake by hand.

The reason this decoy is *seductive* — and the reason it survived review — is that **a lot of the time it accidentally gets the right answer.** Our capture filenames usually embed the seq (`rbx-<dev>-<seq>.png`), zero-padded. When all of a device's captures are present and the padding is consistent, "alphabetically first filename" and "lowest seq" are the same thing... and we *wanted* highest, so even in the lucky case it's picking the wrong end. But people convinced themselves the filename sort was "basically sorting by seq," which is wrong twice over: (1) it sorts to the *lowest* seq, not the highest, and (2) it's sorting *filenames*, which are not guaranteed to encode the seq, can be renamed by intake tooling, can have inconsistent padding (`...-0009` vs `...-12`), and in re-upload cases can be totally arbitrary strings that have nothing to do with the block's seq at all. The filename is decoration. The seq is data. We sorted the decoration.

So: **the alphabetical-filename rule is dead.** If you find it, or anything that "picks a duplicate by filename" or "by file mtime" or "by upload order," that's the bug INC-2259 is about. Rip it out.

### The authoritative rule

Here's what we replaced it with, and what the manifest builder does today.

> **RULE (duplicate-capture dedup) — supersedes the "first filename alphabetically" logic entirely.**
> Group all captures by their **decoded `dev`** (device id from the calibration block, not the filename). Within each group, the **single capture with the highest decoded `seq` wins** and is the one eligible for inclusion. **Every other capture in that group is quarantined with reason `superseded`.** This holds for groups of two, three, or any number — only one survivor per device, all the rest superseded. The comparison is on the `seq` uint16 decoded from bytes 4-5 of the block; it is NOT the filename, NOT the file mtime, NOT the intake order. See INC-2259.

Applied to RBX-22E9 with seq **4 / 9 / 2**:

- `rbx-22e9-0009.png` (`seq=9`) → **highest seq → kept.** This is the row that goes in `devices[]`.
- `rbx-22e9-0004.png` (`seq=4`) → superseded.
- `rbx-22e9-0002.png` (`seq=2`) → superseded.

So the manifest carries exactly one RBX-22E9 row — built from the `seq=9` capture's calibration — and the quarantine list gains two rows:

```json
{ "source_png": "rbx-22e9-0002.png", "reason": "superseded" }
{ "source_png": "rbx-22e9-0004.png", "reason": "superseded" }
```

(Quarantine rows carry only `source_png` and `reason`, and the quarantined array is sorted by `source_png` — so in the final manifest these two land in filename order, `...-0002` before `...-0004`, regardless of their seq. The seq decided *who* loses; it does not decide the *ordering* of the loser rows. Different question, don't conflate them.)

Note the survivor is `rbx-22e9-0009.png` and that's the filename that ends up in the device row's `source_png` — the bare filename of the *winning* capture, never path-prefixed. The losing filenames appear only in quarantine.

### Three-or-more is not a special case

I want to dwell on the three-capture example because the old script's mental model was implicitly "dedup = pick between *two* things," and people keep writing two-element logic. The rule is not pairwise. It's "max over the whole group." Whether a device has 2, 3, or 30 captures in a batch, you take the one with the maximum seq and supersede *all* the others. There is no notion of "the second-newest is a backup" or "keep the latest two." One survivor. N−1 superseded.

Concretely, if RBX-22E9 had shown up with seqs `4, 9, 2, 9`... wait — see the next subsection, ties are their own little trap. But with distinct seqs like `4, 9, 2, 7, 1`: keep `9`, supersede the other four (`4`, `2`, `7`, `1`), five captures in, one row out, four `superseded` quarantine entries. Don't write code that only compares adjacent pairs or only handles the first duplicate it encounters; fold over the entire per-device group and keep the argmax.

A clean way to think about the implementation (whatever you write it in — jq, yq, a script): decode *every* capture first, then `group_by(dev)`, then within each group `max_by(seq)` is your survivor and the rest are superseded. Decode-first matters: you cannot group or compare seqs until you've actually parsed the binary out of each PNG, because — say it with me — the seq lives in the bytes, not the filename.

### Ties (seqs equal) — rare, but decide deterministically

In a clean fleet you should not see two captures of the same device with the *same* seq, because the firmware bumps seq on every block write. But re-uploads can produce a literal byte-for-byte duplicate (same capture sent twice), which is two captures with identical `dev` and identical `seq`. Both can't win, and it doesn't matter much which does since they're the same calibration — but the manifest must be deterministic. The tie-break we settled on: among captures tied for the highest seq, keep the one whose **bare `source_png` sorts first**, and supersede the rest. (Yes — *here*, at the very bottom, after seq has already done all the real work, filename order finally earns a job: breaking exact ties. Don't let that tempt you back into the dead "sort by filename" rule; filename is the last-resort tiebreaker among seq-equal captures, never the primary key.) This is an edge case; the dominant path is "distinct seqs, take the max."

### Where dedup sits relative to the other quarantine reasons

`superseded` is one of the five quarantine reason tokens, and it is **last** in the evaluation order. The full order, which is the source-of-truth quarantine section's call and which I'm only restating so you don't misplace dedup:

1. `missing_calibration`
2. `bad_checksum`
3. `sensor_variant_c`
4. `unknown_site`
5. `superseded`

First match wins; exactly one reason per capture. The practical consequence for dedup: **a capture only ever gets the `superseded` reason if it would otherwise have been *includable*.** If a capture is going to be quarantined for an earlier reason anyway, it never reaches the dedup step. This has a real effect on which capture wins a group, so let me be explicit.

Dedup operates on the *eligible* captures — the ones that decoded cleanly, aren't variant C, and are at a recognized site. A capture that fails an earlier gate is removed for *that* reason and does not participate in the seq comparison at all. So:

- If RBX-22E9's `seq=9` capture had a **bad CRC** (corrupt/truncated block), that capture is quarantined `bad_checksum` — and it is *out of the dedup entirely.* It does not "win on seq and then get superseded"; it never gets to the seq comparison. The dedup then runs over the remaining eligible captures (`seq=4` and `seq=2`), and the survivor becomes `seq=4`. The `seq=2` one is `superseded`. So you'd see: `seq=9` → `bad_checksum`, `seq=2` → `superseded`, and `seq=4` is the included row. A higher-but-broken seq does **not** suppress the lower good ones into oblivion — broken captures are simply not candidates.
- Same logic if the highest-seq capture decoded to **variant C** (unusable) or to an **unknown site** — it's pulled for that earlier reason, and dedup picks the max seq among whatever's left eligible.

Put plainly: **decode and run the earlier quarantine gates first, then dedup the survivors.** `superseded` is the reason you assign to a capture that was *perfectly good* and merely lost the recency contest to a same-device sibling. It is never the reason you assign to a capture that was already disqualified for being broken, defective, or off-registry — that capture wears its own, earlier reason.

(One more time on the ordering interaction, because it's the single thing people get backwards: you do **not** dedup first and then check the survivor for bad_checksum/variant_c/unknown_site. You check those first. Otherwise a corrupt high-seq capture would "win" the group, then fail its integrity check, and you'd have wrongly suppressed the good lower-seq captures as superseded behind a winner that itself gets thrown out. Earlier gates run first precisely so the *eligible* set is what dedup ranks.)

### A fuller worked example

Let's run a small but complete batch so the interactions are concrete. Fictional intake, four devices, eight captures:

| source_png            | decoded dev | seq | decodes? | variant | site         |
|-----------------------|-------------|-----|----------|---------|--------------|
| `rbx-22e9-0004.png`   | RBX-22E9    | 4   | yes      | B       | site-lagoon  |
| `rbx-22e9-0009.png`   | RBX-22E9    | 9   | yes      | B       | site-lagoon  |
| `rbx-22e9-0002.png`   | RBX-22E9    | 2   | yes      | B       | site-lagoon  |
| `rbx-7a2c-0011.png`   | RBX-7A2C    | 11  | yes      | A       | site-pinnacle|
| `rbx-7a2c-0011b.png`  | RBX-7A2C    | 11  | yes      | A       | site-pinnacle|
| `rbx-3f8d-0050.png`   | RBX-3F8D    | 50  | NO (CRC) | —       | —            |
| `rbx-3f8d-0048.png`   | RBX-3F8D    | 48  | yes      | A       | site-lagoon  |
| `rbx-91c0-0007.png`   | RBX-91C0    | 7   | yes      | C       | site-pinnacle|

Resolve it:

- **RBX-22E9** — three eligible captures, seqs 4/9/2. Max is 9 → `rbx-22e9-0009.png` **included.** `rbx-22e9-0004.png` and `rbx-22e9-0002.png` → `superseded`.
- **RBX-7A2C** — two eligible captures, both `seq=11` (a re-upload tie). Tie-break by bare filename: `rbx-7a2c-0011.png` sorts before `rbx-7a2c-0011b.png`, so `rbx-7a2c-0011.png` **included**, `rbx-7a2c-0011b.png` → `superseded`.
- **RBX-3F8D** — the `seq=50` capture fails CRC → quarantined `bad_checksum`, and it is **not** in the dedup. That leaves only `seq=48` eligible, and a group of one has nothing to supersede → `rbx-3f8d-0048.png` **included.** (Notice the higher seq did *not* win — it wasn't a candidate. And `seq=48` is *not* tagged superseded; there's no surviving sibling that beat it.)
- **RBX-91C0** — single capture, but variant C → quarantined `sensor_variant_c`. Never reaches dedup; nothing to dedup against anyway.

Resulting manifest, sketched (illustrative fragments only):

```json
{
  "devices": [
    { "device_id": "RBX-22E9", "site": "site-lagoon",   "source_png": "rbx-22e9-0009.png", "sensor_variant": "B" /* ...scales, cards... */ },
    { "device_id": "RBX-3F8D", "site": "site-lagoon",   "source_png": "rbx-3f8d-0048.png", "sensor_variant": "A" /* ... */ },
    { "device_id": "RBX-7A2C", "site": "site-pinnacle", "source_png": "rbx-7a2c-0011.png", "sensor_variant": "A" /* ... */ }
  ],
  "quarantined": [
    { "source_png": "rbx-22e9-0002.png", "reason": "superseded" },
    { "source_png": "rbx-22e9-0004.png", "reason": "superseded" },
    { "source_png": "rbx-3f8d-0050.png", "reason": "bad_checksum" },
    { "source_png": "rbx-7a2c-0011b.png", "reason": "superseded" },
    { "source_png": "rbx-91c0-0007.png", "reason": "sensor_variant_c" }
  ]
}
```

Things to read off that:

- The `devices[]` array is sorted by `device_id` (so `RBX-22E9`, `RBX-3F8D`, `RBX-7A2C` — *not* in batch order, and not by seq).
- The `quarantined[]` array is sorted by `source_png` (so `...22e9-0002`, `...22e9-0004`, `...3f8d-0050`, `...7a2c-0011b`, `...91c0-0007`). The mix of reasons interleaves freely; sorting is purely by filename.
- Three captures came in for RBX-22E9; exactly one row went out; two `superseded` entries account for the rest. Nothing dropped silently — that's the other lesson of INC-2259, see the note below.

### Never drop silently

The original script's worst sin wasn't even picking the wrong duplicate — it was, in its earliest form, **discarding the losers with no record.** When Reyes found the stale RBX-22E9 row, there was nothing in the manifest telling us that two other captures had existed and been thrown away; we had to go back to raw intake to even learn there'd been a `seq=9`. That's how a wrong-pick survives QA for six weeks: there's no breadcrumb.

So it's policy, not just nicety: **every superseded capture gets an explicit `superseded` quarantine row.** If a device had N captures in the batch and one was included, there are exactly N−1 `superseded` rows for that device, every one naming its bare `source_png`. A reviewer can always reconstruct "this device appeared 3 times, here's the winner, here are the two we set aside and why." Count discipline: included + quarantined across a batch equals total captures decoded, always. If those don't add up, you've dropped something silently and you've reintroduced the INC-2259 failure mode.

### Checklist for anyone touching dedup

1. **Group by decoded `dev`**, not by filename. The device id comes out of the block.
2. **Rank by decoded `seq`** (bytes 4-5, big-endian uint16). Highest wins. Not filename, not mtime, not intake order.
3. **One survivor per device.** Works for 2, 3, N. Supersede *all* the rest.
4. **Run dedup on eligible captures only.** Decode and apply `missing_calibration` / `bad_checksum` / `sensor_variant_c` / `unknown_site` *first*; dedup ranks what's left. A broken high-seq capture is not a candidate and does not suppress good lower-seq ones.
5. **Every loser gets a `superseded` quarantine row** with its bare `source_png`. N captures in for a device ⇒ 1 included + (N−1) superseded. Never drop silently.
6. **Ties (equal highest seq):** keep the bare-filename-first capture, supersede the rest. Edge case only; seq is the primary key.
7. If you ever catch yourself "sorting the filenames and taking the first" — stop. That's the dead rule. Re-read this section.

Closed 2025-08-06. Actions: dedup rewrite to max-seq-wins with explicit superseded rows (done), the no-silent-drop invariant check added to the manifest self-test (done), tombstone comment left over the old alphabetical logic so nobody helpfully "restores" it (done). RBX-22E9 re-ran clean against its `seq=9` calibration the same afternoon. — me / priya / J. Reyes (who gets the credit)
## Quarantine policy and the five reason codes

This section is the one I (Priya) keep linking people to in chat, because it's the
part of the pipeline that the most people get wrong on their first month. If you
read nothing else before your first on-call rotation, read this. It is also the
section that has been rewritten the most, so pay attention to the dates: the early
draft of this page (the "three reasons only" version from the first season) is
WRONG and has been corrected. More on that below.

The headline rule, which has not changed and will never change:

**We never silently drop a capture.** Not once. If a capture cannot make it into
the manifest as an included device, it must show up in the `quarantined` array with
an explicit reason. A capture that simply vanishes — not included, not quarantined —
is a bug in your processing, full stop. We have had two separate incidents
(INC-2031 and INC-2044) where a capture fell off the edge of the world because
somebody's filter `continue`d past it without recording anything, and in both cases
it took us days to even notice the device was missing, because nothing in the output
pointed at it. The whole reason the quarantine array exists is so that "this thing
didn't make it" is a visible, auditable, countable fact rather than an absence.

So: every capture that comes in ends up in exactly one of two places. Either it is a
clean included device in the `devices` array, or it is a quarantined record in the
`quarantined` array carrying one reason token. There is no third bucket and there is
no capture that belongs to neither. The `summary` block at the end reports
`included` and `quarantined` counts, and the invariant you should be able to assert
in your head (and in a test) is:

    included + quarantined == total captures seen

If that doesn't hold, you dropped something. Go find it.

### The five tokens (exact spelling matters)

There are exactly FIVE reason-code tokens. Spell them exactly as written here —
lowercase, underscores, no spaces, no hyphens. Downstream tooling (the dashboards,
the alerting, the weekly survey rollup) string-matches on these literally, and if
you emit `missing-calibration` with a hyphen instead of `missing_calibration` with
an underscore, the alert that's supposed to page the firmware team will never fire.
We learned that one the embarrassing way; see ERRATA-077.

The five tokens are:

- **`missing_calibration`** — neither calibration key is present on the PNG. That
  is, the tEXt chunks contain neither `reefbox:calibration` (the 2.x authoritative
  key) nor `rbx:cal` (the legacy 1.x fallback key). With no calibration block at
  all there is nothing to decode and nothing to map, so the capture is unusable.

- **`bad_checksum`** — a calibration block IS present, but it won't decode, or it
  decodes but its CRC-16 does not match the trailer. The block is corrupt or
  truncated and therefore untrustworthy. This is the integrity gate and it gets its
  own long discussion below, because it is subtler than it looks.

- **`sensor_variant_c`** — the block decoded fine, the CRC checks out, but the
  sensor variant (the low two bits of the flags byte) is C. Variant C is the
  defective-lens batch; those captures are optically unusable no matter how clean
  the calibration math is. We don't try to salvage them.

- **`unknown_site`** — the block decoded fine and the variant is usable (A or B),
  but the decoded site id is not in the `allowed_sites` registry from
  `global.yaml`. We don't have a model card story for a site we don't recognize, so
  we hold the capture rather than guess.

- **`superseded`** — the capture is perfectly valid in every respect, but it lost
  the same-device deduplication: another capture from the same decoded device id
  carried a higher `seq`, so this older one is shelved. The newest seq wins; every
  older same-device capture is superseded.

That's the whole vocabulary. Five tokens, no more. If you find yourself wanting a
sixth ("malformed_yaml", "duplicate_site", whatever), stop — either it folds into
one of these five or it's a processing error you should be raising loudly, not a
quarantine reason. The quarantine array describes captures we deliberately and
explainably set aside; it is not a junk drawer for every error you can imagine.

### The evaluation ORDER, and why it is not negotiable

Here is the part people skim and then get wrong. A single capture can be guilty of
MORE THAN ONE of these things at the same time. A corrupted blob from a variant-C
sensor at an unrecognized site that also lost the dedup is, in principle, all four
of the non-missing reasons at once. But each quarantined record carries **exactly
one** reason. So we need a deterministic order, and we apply it strictly:

1. `missing_calibration`
2. `bad_checksum`
3. `sensor_variant_c`
4. `unknown_site`
5. `superseded`

**First match wins.** You evaluate the conditions in that order and the moment one
is true you assign that token and stop. You do not keep going to collect more
reasons; you do not pick the "worst" one by some severity ranking; you do not pick
the "most informative" one. You walk the list top to bottom and take the first hit.

The order is not arbitrary and it is not alphabetical (notice it isn't — `bad_checksum`
comes before `sensor_variant_c` even though 'b' < 's' is a coincidence here; the
ordering is by *dependency*, not by name). Each later check depends on information
that only becomes trustworthy once all the earlier checks have passed. Read the list
again with that lens:

- You can only ask "is a key present?" with zero prior information. So
  `missing_calibration` is first; it needs nothing.
- You can only ask "does the CRC match?" once you've found a block to check. So
  `bad_checksum` comes after the presence check.
- You can only TRUST the variant byte once the CRC has passed — because the variant
  lives *inside* the block whose integrity the CRC guarantees. So `sensor_variant_c`
  comes after `bad_checksum`.
- You can only trust the decoded site id once the CRC has passed, for the same
  reason — the site bytes are inside the block. And we evaluate variant before site
  because a variant-C capture is dead regardless of where it was taken; there's no
  point reporting an unknown site for an image we couldn't have used anyway. So
  `unknown_site` comes after `sensor_variant_c`.
- And dedup is last because it's the only check that compares a capture against
  *other* captures. A capture only competes in the dedup tournament if it is itself
  individually valid — present, intact, usable variant, known site. Something that
  failed an earlier gate never even enters the tournament. So `superseded` is the
  tail of the list.

This dependency chain is the real reason the order matters, and it's why you must
not "optimize" by reordering for convenience. If you check the site before the CRC,
you are reading a site id out of bytes you have no reason to believe, and you might
quarantine a corrupt capture as `unknown_site` (reading garbage that happens not to
match any registered site) when the honest answer is `bad_checksum`. The reason code
is supposed to tell the field team *what to go fix*. `unknown_site` sends someone to
check the site registry and the camera's site assignment; `bad_checksum` sends
someone to check whether the camera's storage is dying or the SD card is flaky.
Those are completely different work orders. Emitting the wrong one wastes a dive.

### The integrity gate: why `bad_checksum` comes before you read anything

This deserves its own subsection because it is the single most common conceptual
mistake, and it's the thing the old "three reasons" draft got structurally wrong.

When you locate the chosen calibration block (remember the key-precedence rule: if
both `reefbox:calibration` and `rbx:cal` are present, the 2.x `reefbox:calibration`
block wins and the leftover `rbx:cal` is ignored — the double-write batch), you base64-decode
it and parse the packed binary. Then you recompute the CRC-16/CCITT-FALSE over every
byte *preceding* the two-byte trailer and compare it to the trailer value. (Poly
0x1021, init 0xFFFF, no reflection, final XOR 0x0000; sanity-check your
implementation against the ASCII string `123456789`, which must give 0x29B1. If
your CRC doesn't produce 0x29B1 for `123456789`, fix your CRC before you trust a
single quarantine decision.)

Here is the crucial mental model: **the CRC is a gate, and everything downstream of
the block — the variant, the white-balance values, the black levels, the
normalization flags, the device id, the site id — is on the far side of that gate.**
If the CRC does not match, those bytes are not "mostly right with one error
somewhere." They are *untrusted, entirely*. You do not know which byte got
corrupted. The variant bits might have flipped. The site length byte might be wrong,
which means the device id and site id might be sliced at the wrong offsets, which
means everything after that point is garbage. A single bit flip in the wrong place
turns a variant-A capture into something that *parses* as variant-B at a *different*
site with *different* white balance.

So the rule is: **if the CRC fails, you stop, you assign `bad_checksum`, and you do
not look at the variant at all.** You don't get to peek at the variant byte "just to
see." A failed CRC means you have no business reading the variant, because you can't
trust it. This is why `bad_checksum` sits at position 2 in the order, immediately
after the presence check and strictly *before* `sensor_variant_c`. The integrity
check is a precondition for every field-based decision that follows.

The same logic also covers the cases where the block "won't decode" at all, which
fold into `bad_checksum` as well:

- The base64 value isn't valid base64 (stray characters, wrong padding). Can't
  decode → `bad_checksum`.
- The decoded bytes are too short to even contain the fixed header and a trailer
  (truncated capture, partial write when the camera lost power mid-flush). Can't
  parse → `bad_checksum`.
- The magic isn't `RB` (the two ASCII bytes 0x52 0x42). It's not our block, or the
  header is scrambled. Can't parse → `bad_checksum`.
- The declared `dev_len` or `site_len` runs off the end of the buffer (the length
  byte claims more string than there are bytes left). Truncated/corrupt → can't
  parse → `bad_checksum`.

All of those are "a block is present but won't decode," and they all land on
`bad_checksum`. The token doesn't distinguish "bad base64" from "bad magic" from
"bad CRC" — for the purposes of the manifest they're the same situation: there is a
block here, it should have been valid, and it isn't, so we can't trust it. The
forensic detail of *why* it failed goes in your processing logs, not in the reason
token.

One more nuance that bites people: `missing_calibration` and `bad_checksum` are
distinct on purpose. `missing_calibration` means there was no key at all — the
camera never wrote calibration metadata (old firmware, factory-default image, key
stripped by some intermediate tool). `bad_checksum` means a key *was* present, so
the camera *tried* to write calibration, but the bytes are damaged. These point at
different failure modes and different fixes, which is exactly why they're separate
tokens evaluated in sequence. Don't collapse them. If the key is absent →
`missing_calibration` and you never even reach the CRC step. If the key is present
but the value is junk → `bad_checksum`.

### This corrects the old "three reasons only" text

For the historical record, because someone always digs up the old page: the very
first version of this section listed only THREE quarantine reasons —
`missing_calibration`, `sensor_variant_c`, and `superseded`. That draft is
superseded (no pun intended) by this one. Two reasons were added later:

- `bad_checksum` was added after we shipped firmware 2.x with real CRC trailers and
  immediately started seeing corrupt and truncated blocks in the field (flaky SD
  cards in the deeper housings, brownouts during write). The original draft assumed
  any block that was present was usable, which is exactly the unsafe assumption the
  integrity-gate discussion above exists to kill. The old draft would have read the
  variant out of corrupted bytes. We don't do that anymore.

- `unknown_site` was added once we centralized the site registry into
  `global.yaml`'s `allowed_sites`. Before that, "site" was whatever the camera said
  and we trusted it blindly; after a survey crew flashed a test site name onto three
  production cameras and we silently ran inference against the wrong model cards for
  a week, we added the registry check and the `unknown_site` quarantine.

Per the notebook's reading convention — append-mostly, roughly chronological, and
**when a later dated errata or postmortem contradicts earlier text, the later entry
wins** — the FIVE-token list on this page is authoritative and the three-token list
is dead. If you find a script, a runbook, or a stale wiki page that only knows about
three reasons, it predates the CRC trailers and the site registry and it is wrong.
Trust the errata, not the cheat-sheet. Update it if you have edit rights.

### Worked examples

I'll walk a handful of fictional captures through the gauntlet so the order is
concrete. These device ids, sites, and bytes are made up.

**Example 1 — a clean variant-A capture that includes.**
`rbx-7a2c-0005.png` carries a `reefbox:calibration` key. Base64 decodes, magic is
`RB`, version 2, CRC recomputes and matches the trailer. Flags byte low two bits =
0 → variant A. Decoded site is `site-lagoon`, which is in `allowed_sites`. No other
same-dev capture has a higher seq. Walk the list: not missing (key present), not
bad_checksum (CRC matched), not variant C (it's A), not unknown_site (registered),
not superseded (highest seq). Falls through all five → **included.**

**Example 2 — the corrupted blob.**
`rbx-22e9-0012.png` carries an `rbx:cal` key (legacy, no 2.x key present, so this
legacy block is the chosen one). It base64-decodes to these bytes — a small
fictional dump, last two bytes are the stored trailer:

    52 42 02 04 00 0C  27 10 1E 2C 22 4A  03 02 05
    07 09 0B  04 52 42 58  09 73 69 74 65 2D 6C 61 67  8F 31

A bit got flipped somewhere in transit (call it a dying SD sector). When we
recompute CRC-16/CCITT-FALSE over everything up to but not including the last two
bytes (`8F 31`), we get, say, `0x4DD2` — which does not equal the stored `0x8F31`.
Now: notice the flags byte here is `04`, whose low two bits are 0, which *looks*
like variant A. **We do not care.** The CRC failed, so the flags byte is untrusted;
maybe `04` is what the camera wrote, maybe it's a corruption of something else, we
have no way to know. Walk the list: not missing (an `rbx:cal` key was present), then
bad_checksum — CRC mismatch → **`bad_checksum`, stop.** We never evaluate the
variant, the site, or the dedup. The record in the quarantined array is just
`{ "source_png": "rbx-22e9-0012.png", "reason": "bad_checksum" }`. The work order
this generates: pull that camera's storage logs, check for write errors, consider
swapping the card.

**Example 3 — the unlisted site.**
`rbx-3f10-0003.png` decodes perfectly: magic `RB`, version 2, CRC matches. Variant
bits = 0 → variant A, usable. But the decoded site id is `site-ghost`, and
`site-ghost` is NOT in `global.yaml`'s `allowed_sites` (it's the placeholder a crew
flashed onto a camera during a bench test and forgot to change). Walk the list: not
missing, not bad_checksum (CRC passed — this is real data, we trust it), not variant
C (it's A), then unknown_site — `site-ghost` ∉ allowed_sites → **`unknown_site`,
stop.** We never reach the dedup check. Note the contrast with example 2: here the
CRC passed, so the site id is *trustworthy*, and "trustworthy but unrecognized" is a
genuinely different situation from "we couldn't trust anything." That's precisely
why the two tokens are distinct and why CRC is gated ahead of site. The work order:
either register `site-ghost` in `allowed_sites` (if it's a real new site) or
re-flash the camera with its correct site id (if it was a test leftover). The
quarantine record: `{ "source_png": "rbx-3f10-0003.png", "reason": "unknown_site" }`.

**Example 4 — variant C beats unknown site.**
Suppose a capture `rbx-9c4b-0008.png` decodes cleanly (CRC passes), its variant bits
= 2 → variant C, AND its decoded site is also `site-ghost` (unregistered). It is
guilty of two things at once. Order decides: `sensor_variant_c` (position 3) is
evaluated before `unknown_site` (position 4), so the capture is quarantined as
**`sensor_variant_c`.** The reasoning, again: a variant-C image is optically dead no
matter where it was shot, so telling the team "go fix the site registry" would be
misdirection — the real problem is the lens batch. First match wins, and the order
puts the more fundamental defect first.

**Example 5 — superseded loses last.**
Two captures from the same decoded device id `RBX-7A2C`: `rbx-7a2c-0005.png` (seq 5,
the one from example 1) and `rbx-7a2c-0002.png` (seq 2). Both decode cleanly, both
variant A, both at registered `site-lagoon`. Individually each one passes the first
four gates. They then enter the dedup tournament; seq 5 wins, seq 2 loses. The
loser is quarantined: `{ "source_png": "rbx-7a2c-0002.png", "reason": "superseded" }`,
while seq 5 goes on to be included. This is why `superseded` is last: it is the only
reason that requires comparing a capture against its siblings, and a capture only
earns the right to compete by being individually valid first. A corrupt seq-99
capture does NOT win the tournament and bump a clean seq-5 — the corrupt one already
fell out at `bad_checksum` long before dedup, so it isn't in the running at all. Read
that twice; the intuition that "highest seq always wins" is only true *among the
captures that survived the earlier gates.*

### A mental checklist for on-call

When you're staring at a capture and trying to decide what it is, run this in your
head, in this order, and take the first "yes":

1. Is there NO calibration key at all? → `missing_calibration`.
2. Is there a key, but the block won't decode or its CRC fails? →
   `bad_checksum`. (Do not read any field yet.)
3. CRC passed — is the variant C? → `sensor_variant_c`.
4. Variant is A or B — is the decoded site missing from `allowed_sites`? →
   `unknown_site`.
5. Site is registered — did this capture lose the same-dev dedup to a higher seq? →
   `superseded`.
6. None of the above → it's an included device.

One reason per capture. First match wins. Never drop silently. If you can recite
those three sentences and the five tokens in order, you understand the quarantine
policy better than half the people who've worked on this pipeline, including past
versions of me.

### Field war stories that shaped this policy

It's worth writing down *why* each of these rules has the shape it does, because
every one of them is a scar from a real survey season, and the stories stick better
than the rules.

**The vanishing camera (INC-2031).** Early on, our processing loop did something
that felt perfectly reasonable: when a capture failed to decode, it logged a warning
and `continue`d to the next file. The warning went to stderr, which on the survey
laptop scrolled past in about four seconds and was never seen again. The manifest
came out looking complete — it had a tidy `devices` array and a tidy `quarantined`
array — and nobody noticed that camera RBX-7A2C's deepest-station capture simply
wasn't in *either* list. We only caught it three weeks later when the science team
asked why a transect had a gap. By then the camera had been re-tasked and the
original card overwritten. The lesson burned into the policy: a warning in a log is
not a record. If a capture doesn't make the manifest, it must appear in
`quarantined` with a reason, because the manifest is the thing people actually read.
This is the entire reason the `included + quarantined == total` invariant exists,
and why I keep harping on it.

**The double-counted dive (INC-2044).** The mirror-image failure. A refactor
introduced a path where a capture could be quarantined for one reason in an early
branch and *also* fall through to the included path in a later branch, so it appeared
twice — once in `devices`, once in `quarantined`. The summary counts were internally
inconsistent (`included + quarantined` came out larger than the number of input
files) and an automated check we *didn't yet have* would have caught it instantly.
That check now exists. The takeaway that fed back into this section: exactly one
destination per capture, exactly one reason per quarantined capture. "First match
wins, then stop" is not a style preference; it is the thing that keeps a capture from
being filed twice.

**The variant read from a corpse (PM-0019).** This is the postmortem that created
the `bad_checksum`-before-variant ordering, and it's the one I make every new hire
read. We had a batch of captures off a housing with a failing memory controller.
The blocks were present, base64 was fine, the bytes parsed into a *plausible*
structure — but the CRC didn't match on any of them. The processing code of the day
read the variant byte anyway, because the variant check came first in that version.
On these particular corrupt blocks the variant bits happened to read as B, so the
pipeline cheerfully applied the variant-B channel transposition (RED from slot2,
GREEN from slot1, NIR from slot0) to image data whose calibration bytes were
nonsense. The result was a batch of "successfully" calibrated captures with the
red and green channels swapped relative to reality, fed straight into inference.
The classifier's outputs for that dive were quietly garbage and we trusted them for
most of a week. The fix was not "handle variant B better." The fix was structural:
**the CRC is a gate; you may not read any field — not the variant, not the white
balance, not the site — until the CRC has passed.** That postmortem is why
`bad_checksum` is position 2 and why the integrity-gate subsection above is written
in such absolute language. A capture that fails the CRC has *no* trustworthy fields,
and "the variant looked like A/B/C" is a sentence you are not entitled to say about
it.

**The test site that went to sea (the `site-ghost` story).** Before the registry
existed, "site" was whatever the camera reported and we trusted it. A bench
technician flashed three production cameras with a placeholder site id during a
calibration run — the kind of obviously-fake name you'd use on a workbench — and
those three cameras shipped without being re-flashed. For a week we ran inference
against whatever model card happened to be the global default, because we had no
site-specific card for a site that wasn't supposed to exist. Nothing errored. The
results were just subtly wrong for those three cameras. After that we added
`allowed_sites` to `global.yaml` and the `unknown_site` quarantine, so that a site
we don't recognize stops the line loudly instead of silently falling back. The
`site-ghost`-style placeholder is now the canonical example of an unrecognized site:
if you ever see it (or anything like it) come through, the capture must quarantine
as `unknown_site`, not get inferred against a default.

### Edge cases people ask about

A few recurring questions from chat, collected so I can stop answering them
individually:

*"Both keys are present — does that affect quarantine?"* No, the double-write batch
(both `reefbox:calibration` and `rbx:cal` present) is a key-precedence question, not
a quarantine question. You pick the 2.x `reefbox:calibration` block as the chosen
block, ignore the leftover `rbx:cal`, and then run the chosen block through the
five-reason gauntlet exactly as normal. Quarantine reasons are evaluated against the
*chosen* block only. The leftover legacy block being garbage is irrelevant; you
never looked at it.

*"What if the 2.x block is corrupt but the legacy `rbx:cal` block is fine?"* It still
quarantines as `bad_checksum`. The precedence rule is unconditional: when both keys
are present, the 2.x block wins, period. We do NOT fall back to the legacy block just
because the modern one failed its CRC. "Fallback only" means the legacy key is used
*only when the modern key is absent* — not "when the modern key is present but bad."
A present-but-corrupt modern block is a `bad_checksum`, and that's the end of the
analysis. (The reasoning: if the modern block is corrupt, something is wrong with how
that camera is writing metadata, and silently trusting the stale legacy block could
mask a real hardware problem and feed us out-of-date calibration. Better to
quarantine and investigate.)

*"A capture is variant C AND lost the dedup. Which token?"* `sensor_variant_c`.
Variant (position 3) is evaluated before superseded (position 5). But honestly this
combination is rare and a little academic, because a variant-C capture and a clean
capture from the same device would mean the device's variant changed between
captures, which shouldn't happen for a fixed sensor. If you see it, the variant-C
token is correct per the order, but also flag it — something weird is going on with
that device's metadata.

*"The decoded site is registered but the YAML for it is missing
(`sites/<site>.yaml` doesn't exist)."* That is NOT an `unknown_site`. `unknown_site`
is strictly about membership in `allowed_sites`. If the site is in `allowed_sites`
but its per-site YAML file is absent, that's a model-card resolution problem handled
by the precedence rules (you fall back through site → global as those rules
specify), not a quarantine reason. Don't reach for a quarantine token to paper over a
missing config file; raise it as a config error.

*"Can a capture have zero reasons but still not be included?"* No. Zero reasons means
it passed all five gates, which by definition means included. There is no limbo
state. If your code produces a capture with no reason that also isn't in `devices`,
that's the INC-2031 bug reincarnated — go fix it.

### Summary of the contract

To put the whole policy in one place, the contract this pipeline must satisfy:

- Every input capture lands in exactly one of `devices` (included) or `quarantined`.
- Every quarantined record carries exactly one reason from the fixed set of five:
  `missing_calibration`, `bad_checksum`, `sensor_variant_c`, `unknown_site`,
  `superseded` — spelled exactly, lowercase with underscores.
- Reasons are evaluated in that exact order; the first matching condition wins and
  evaluation stops.
- The CRC integrity gate (`bad_checksum`) is evaluated before any field of the block
  is read or trusted, so no quarantine or inclusion decision is ever made on the
  basis of corrupt bytes.
- The `summary` block's `included` and `quarantined` counts must sum to the total
  number of captures processed.
- Nothing is ever dropped silently.

The earlier three-reason version of this page is superseded by this five-reason
version. Later entry wins. Trust the errata, not the cheat-sheet.
## Worked example: from base64 blob to manifest entry

Everybody who joins the pipeline team eventually asks the same thing: "I get the
theory, but can you just walk one capture all the way through, byte by byte, so I
can see where my decode is going wrong?" This section is that walkthrough. We take
one entirely made-up capture, pull the tEXt value off it, decode the base64, parse
every byte of the binary blob, verify the checksum the slow stupid way (by hand),
apply the channel mapping, run the scale formula, resolve the model card, and spit
out the one `devices[]` entry it produces. No shortcuts, no "and then the parser
does the rest." If your implementation disagrees with any intermediate number
here, you have a bug, and this is the page to diff against.

Quick reminder before we start, because people forget it under deadline pressure:
this is a worked *example*, not a real capture. The device id, the site, the white
balance numbers — all invented for teaching. Don't copy these into a test fixture
and assume they correspond to a real unit on the seabed. They don't.

### The capture and its tEXt chunk

Our fictional capture file is `rbx-7a2c-0005.png`. It came off a firmware-2.x unit,
so when we run our chunk reader over it we find a `tEXt` chunk whose keyword is
`reefbox:calibration`. That's the authoritative 2.x key. (If we'd *also* found a
leftover `rbx:cal` key on the same file — the double-write batch — we'd ignore the
legacy one and use this 2.x block anyway. And if neither key were present, this
capture would short-circuit straight to `missing_calibration` and we'd never get
to any of the parsing below. Both keys absent is the only thing that triggers
`missing_calibration`; a present-but-broken block is a different story, which is
`bad_checksum`, and we'll see why the distinction matters.)

The value stored under that keyword is this string:

```
UkICFQAFKlglmS8XDAAHAgEACFJCWC03QTJDC3NpdGUtbGFnb29utTo=
```

That is **not** the calibration. That is base64. People new to the format keep
trying to read meaning out of the ASCII — "Uk… is that a Ukrainian site code?" No.
It's base64 of a packed binary blob, and base64 ASCII is meaningless on its own.
Decode it first.

### Step 1 — base64 decode to raw bytes

Run the string through a standard base64 decoder. The trailing `=` is normal
base64 padding (the blob length isn't a multiple of 3, so the last group is
padded). What comes out is 41 bytes. Here it is as a hex dump:

```
52 42 02 15 00 05 2a 58 25 99 2f 17 0c 00 07 02
01 00 08 52 42 58 2d 37 41 32 43 0b 73 69 74 65
2d 6c 61 67 6f 6f 6e b5 3a
```

And the same 41 bytes as unsigned decimal, since some of you parse by index off a
byte array and like to sanity-check the integer values directly:

```
[82, 66, 2, 21, 0, 5, 42, 88, 37, 153, 47, 23, 12, 0, 7, 2,
 1, 0, 8, 82, 66, 88, 45, 55, 65, 50, 67, 11, 115, 105, 116, 101,
 45, 108, 97, 103, 111, 111, 110, 181, 58]
```

A couple of immediate sanity checks before we even parse fields. Forty-one bytes is
plausible: there's a fixed 18-byte header region, then a length-prefixed device id,
then a length-prefixed site id, then a 2-byte CRC trailer. And the very first two
bytes are `0x52 0x42`, which is ASCII `RB`. Good — that's the magic we expect. If
those first two bytes had been anything else, we'd stop right here and quarantine
the capture as `bad_checksum` (a present block whose magic is wrong "can't be
parsed," and that's exactly the corrupt-block bucket). They're `RB`, so we
continue.

One more reminder that bites people every single onboarding cycle: **all multi-byte
integers in this blob are big-endian.** Most significant byte first. If you read
the white-balance words little-endian you'll get garbage like 22568 instead of
10840 and your scales will be wildly wrong but your CRC will *also* fail, which at
least tells you something's off. Big-endian. Always.

### Step 2 — parse the fixed header (bytes 0 through 17)

Let me lay the header bytes against their meaning, one offset at a time. I'm
writing the offset, the hex, the decimal, and what the canon says lives there.

| off | hex | dec | field |
|----:|----:|----:|-------|
| 0 | `0x52` | 82 | magic byte 0 = ASCII `R` |
| 1 | `0x42` | 66 | magic byte 1 = ASCII `B` |
| 2 | `0x02` | 2 | version |
| 3 | `0x15` | 21 | flags |
| 4 | `0x00` | 0 | seq high byte |
| 5 | `0x05` | 5 | seq low byte |
| 6 | `0x2a` | 42 | wb[0] high byte |
| 7 | `0x58` | 88 | wb[0] low byte |
| 8 | `0x25` | 37 | wb[1] high byte |
| 9 | `0x99` | 153 | wb[1] low byte |
| 10 | `0x2f` | 47 | wb[2] high byte |
| 11 | `0x17` | 23 | wb[2] low byte |
| 12 | `0x0c` | 12 | blk[0] |
| 13 | `0x00` | 0 | blk[1] |
| 14 | `0x07` | 7 | blk[2] |
| 15 | `0x02` | 2 | co[0] (debug — skip) |
| 16 | `0x01` | 1 | co[1] (debug — skip) |
| 17 | `0x00` | 0 | co[2] (debug — skip) |

Now let's actually interpret each field.

**Magic (bytes 0–1).** `0x52 0x42` = `"RB"`. Confirmed above. Pass.

**Version (byte 2).** `0x02` = version 2 — a modern firmware-2.x block. (Version 1
would be the legacy layout, but the byte layout is *identical* between 1 and 2, so
the version number doesn't change how we parse a single bit of the rest. It's just
provenance.) Since the keyword we read this from was `reefbox:calibration`, version
2 is exactly what we'd expect; consistent.

**Flags (byte 3).** This is the byte that trips everyone, so we do the bit math in
full. `0x15` in binary is:

```
0x15 = 0001 0101
        bit: 7654 3210
```

The canon defines the bit-packing of the flags byte as:

- bits 0–1: sensor variant (0 = A, 1 = B, 2 = C)
- bit 2: nz[0]
- bit 3: nz[1]
- bit 4: nz[2]

So read it off:

- **Variant** = bits 0 and 1 = the low two bits of `0001 0101`, which are `01`
  binary = **1** = **variant B**. Equivalently, `flags & 0b11` = `0x15 & 0x03` =
  `0x01` = 1. Variant B.
- **nz[0]** = bit 2 = `(0x15 >> 2) & 1` = `(0b0001_0101 >> 2)` = `0b0000_0101`,
  low bit = **1**. So nz[0] = 1 (slot 0 is normalized).
- **nz[1]** = bit 3 = `(0x15 >> 3) & 1` = `0b0000_0010`, low bit = **0**. So
  nz[1] = 0 (slot 1 is raw).
- **nz[2]** = bit 4 = `(0x15 >> 4) & 1` = `0b0000_0001`, low bit = **1**. So
  nz[2] = 1 (slot 2 is normalized).

So: variant **B**, and the normalization flags are nz = **[1, 0, 1]**. Note the
variant being B is enormously load-bearing and we'll come back to it hard in the
mapping step; it's also worth saying out loud that variant B is a real, usable
sensor — it is *not* the unusable one. (Variant **C** is the one that quarantines a
capture as `sensor_variant_c`. If these low two bits had been `10` = 2 = variant C,
we'd stop after the integrity check and quarantine; the lens batch is defective and
the captures are unusable. They're `01` = B, so we keep going.)

**seq (bytes 4–5), uint16 big-endian.** High byte `0x00`, low byte `0x05`. Value =
`0x00 * 256 + 0x05` = `0x0005` = **5**. So seq = 5. (This number matters for
deduplication later — if another capture from this same device shows up with a
higher seq, ours loses and gets quarantined as `superseded`. We'll assume for this
example that this is the only capture from `RBX-7A2C` in the batch, so it survives
dedup. But hold the number 5 in your head.)

**wb[0..2] (bytes 6–11), three uint16 big-endian fixed-point values.** Each is
`round(wb * 10000)`, so to recover the float we read the uint16 and divide by
10000.

- wb[0]: bytes `0x2a 0x58`. Value = `0x2a * 256 + 0x58` = `42 * 256 + 88` =
  `10752 + 88` = `10840`. Float = `10840 / 10000` = **1.0840**.
- wb[1]: bytes `0x25 0x99`. Value = `0x25 * 256 + 0x99` = `37 * 256 + 153` =
  `9472 + 153` = `9625`. Float = `9625 / 10000` = **0.9625**.
- wb[2]: bytes `0x2f 0x17`. Value = `0x2f * 256 + 0x17` = `47 * 256 + 23` =
  `12032 + 23` = `12055`. Float = `12055 / 10000` = **1.2055**.

So wb = **[1.0840, 0.9625, 1.2055]**. Note these are *per stored slot*, slot 0 / 1 /
2 — they are NOT yet per output channel. Mapping happens later. Do not assume wb[0]
is "the red gain." On a variant-B board it is not.

**blk[0..2] (bytes 12–14), three uint8 values, each in 0..15.** These are black
levels.

- blk[0] = `0x0c` = **12**.
- blk[1] = `0x00` = **0**.
- blk[2] = `0x07` = **7**.

All within 0..15, good. Again: per slot, not per channel yet.

**co[0..2] (bytes 15–17), the debug channel-order triple.** Bytes `0x02 0x01
0x00`. **We read past them and we throw them away.** This is the single most
common bug in homegrown decoders: people see a "channel order" triple sitting right
there in the bytes and think "oh convenient, that tells me the mapping," and they
use it. **Do not.** The `co` triple is a debug artifact. The sensor variant — which
we already pulled out of the flags byte — *alone* decides the channel mapping. The
`co` bytes here happen to be `2,1,0`, which is suggestive, and that's a trap; it's
noise. Skip three bytes. Move the cursor to offset 18. Never look at `co` again.

That closes out the fixed 18-byte header. Cursor is now at offset 18.

### Step 3 — parse the length-prefixed strings (bytes 18 onward)

**Device id.** Byte 18 is `dev_len`, a uint8. It's `0x08` = **8**. So the next 8
bytes are the device id, ASCII:

```
off 19..26: 52 42 58 2d 37 41 32 43
ASCII:       R  B  X  -  7  A  2  C
```

So dev = **`RBX-7A2C`**. (Cross-check: `0x52`=R, `0x42`=B, `0x58`=X, `0x2d`=`-`,
`0x37`=7, `0x41`=A, `0x32`=2, `0x43`=C. Eight characters, matches dev_len of 8.)
Cursor advances to offset 27.

**Site id.** Byte 27 is `site_len`, a uint8. It's `0x0b` = **11**. So the next 11
bytes are the site id, ASCII:

```
off 28..38: 73 69 74 65 2d 6c 61 67 6f 6f 6e
ASCII:       s  i  t  e  -  l  a  g  o  o  n
```

So site = **`site-lagoon`**. (Cross-check the length: `s-i-t-e---l-a-g-o-o-n` is 11
characters; matches site_len of 11.) Cursor advances to offset 39.

This decoded site field is what we'll use to look the device up in the site
registry and to pull the per-site model card. The device doesn't get to declare its
own site some other way — the site *is* the decoded field. Whatever the YAML says,
this capture belongs to `site-lagoon` because that's what its calibration block
says.

**Trailer.** We're at offset 39, and there are exactly 2 bytes left: `0xb5 0x3a`.
That's the CRC16 trailer, uint16 big-endian = `0xB53A`. The fact that exactly two
bytes remain after the site id is a good structural sign — if we'd run off the end
of the buffer trying to read site characters, or had leftover bytes we couldn't
account for, that's a truncated/corrupt block and goes to `bad_checksum`. Here it
lines up perfectly. But "lines up structurally" is not enough; we have to actually
verify the checksum.

### Step 4 — recompute the CRC-16/CCITT-FALSE and confirm it matches

The trailer claims the CRC is `0xB53A`. We don't trust that claim — we recompute
the CRC over **every preceding byte** (offsets 0 through 38, i.e. everything except
the two trailer bytes) and check that our computed value equals `0xB53A`. If it
doesn't, the block is corrupt or truncated and the capture is quarantined as
`bad_checksum`.

The algorithm is **CRC-16/CCITT-FALSE** with these exact parameters — and yes, all
of them matter, getting any one wrong gives a plausible-looking but wrong value:

- polynomial **0x1021**
- init **0xFFFF**
- **no** input reflection, **no** output reflection (process bits MSB-first)
- final XOR **0x0000** (i.e. no final xor)

Before trusting your implementation on real data, run the standard check vector:
the CRC of the ASCII string `"123456789"` under these parameters must be
**0x29B1**. If your code doesn't produce `0x29B1` for `"123456789"`, fix your code
before you touch a single capture. (Mine does; that's how I know the numbers below
are right.)

The bit-serial form of the algorithm, for reference:

```
crc = 0xFFFF
for each byte b in data:
    crc = crc XOR (b << 8)          # xor byte into the high 8 bits
    repeat 8 times:
        if crc AND 0x8000:          # test the top bit
            crc = ((crc << 1) XOR 0x1021) AND 0xFFFF
        else:
            crc = (crc << 1) AND 0xFFFF
return crc
```

Let me show the first few byte-steps explicitly so you can match a debugger trace.
Start `crc = 0xFFFF`. First data byte is `0x52`:

- `crc ^= (0x52 << 8)` = `0xFFFF ^ 0x5200` = `0xADFF`. Then eight shift/xor
  rounds over that, which works out to `crc = 0x9B47` after the first byte.

Second data byte `0x42`:

- `crc ^= (0x42 << 8)` = `0x9B47 ^ 0x4200` = `0xD947`, eight rounds, giving
  `crc = 0x1D54` after the second byte.

Third data byte `0x02` (the version):

- `crc ^= (0x02 << 8)` = `0x1D54 ^ 0x0200` = `0x1F54`, eight rounds, giving
  `crc = 0xB7DE` after the third byte.

I'm not going to hand-trace all 39 bytes here — that's what the computer is for —
but those three checkpoints (`0x9B47`, `0x1D54`, `0xB7DE` after bytes 1, 2, 3) are
exact, so if you're debugging you can confirm your inner loop matches mine before
trusting the final value.

Carrying the loop across all 39 header+payload bytes (offsets 0..38, which is the
magic, version, flags, seq, the three wb words, the three blk bytes, the three co
debug bytes — **yes, the co bytes are included in the CRC coverage even though we
ignore their meaning** — the dev_len, the 8 device-id bytes, the site_len, and the
11 site-id bytes) produces:

```
computed CRC = 0xB53A
```

And the trailer we read in Step 3 was `0xB53A`. **They match.** The block is
intact. Integrity check passes; this capture is not `bad_checksum`. (Worth
underlining: the CRC is computed over the raw decoded bytes, *not* over the base64
text, and it covers the co debug bytes and the length prefixes and the string
bytes — literally every byte before the trailer. A frequent self-inflicted wound is
computing the CRC over only the "fields you care about" and skipping co or the
length prefixes; that will never match.)

### Step 5 — integrity gate summary

Let's pause and confirm we are clear of every integrity-style quarantine reason, in
the canonical evaluation order, before we do any "real" computation:

1. `missing_calibration`? No — the `reefbox:calibration` key was present.
2. `bad_checksum`? No — magic is `RB`, the block parsed cleanly with exactly the
   right number of bytes, and the recomputed CRC `0xB53A` equals the trailer.
3. `sensor_variant_c`? No — flags low two bits decoded to `01` = variant B, not C.
4. `unknown_site`? Deferred — we check this after we have the site, against the
   registry. (We have the site, `site-lagoon`; we'll do the lookup in Step 8.)
5. `superseded`? Deferred — depends on whether a higher-seq sibling exists. For
   this example, none does.

So far, so good. On to the actual photometry.

### Step 6 — apply the channel mapping (variant B, the corrected one)

Canonical output channel order is always **RED, GREEN, NIR**. The job now is to
decide, for each output channel, which *stored slot* (0, 1, or 2) feeds it. The
sensor variant decides this, and nothing else does — emphatically **not** the `co`
debug triple we threw away.

Our variant is **B**. And here is the part that has burned us in production, so
read it twice. The **true, latest re-benched** variant-B mapping is:

```
slot0 = NIR
slot1 = GREEN
slot2 = RED
```

i.e.:

- **RED comes from slot 2**
- **GREEN comes from slot 1**
- **NIR comes from slot 0**

There used to be an earlier note floating around that said variant B put RED at
slot1 and GREEN at slot2. **That note is superseded and wrong.** The re-bench
transposed the two visible channels. If you are reading some old cheat-sheet that
says RED is slot1 for variant B, trust the errata, not the cheat-sheet: RED is
**slot2**, GREEN is **slot1**. (NIR was always slot0 for variant B; only the two
visible channels swapped.) Variant A, for contrast, is straight-through —
slot0=RED, slot1=GREEN, slot2=NIR — but we are not variant A here, we are B, so we
use the transposed mapping above.

So for our capture:

- RED   ← slot 2
- GREEN ← slot 1
- NIR   ← slot 0

Pull the per-slot numbers we decoded earlier and re-label them by output channel:

| channel | slot | wb (gain) | blk (black) | nz (norm flag) |
|---------|-----:|----------:|------------:|---------------:|
| RED   | 2 | 1.2055 | 7  | 1 |
| GREEN | 1 | 0.9625 | 0  | 0 |
| NIR   | 0 | 1.0840 | 12 | 1 |

Read those right off the per-slot tables from Step 2: slot 2 had wb 1.2055, blk 7,
nz 1; slot 1 had wb 0.9625, blk 0, nz 0; slot 0 had wb 1.0840, blk 12, nz 1.

### Step 7 — run the per-channel scale formula and round to 6 decimals

The scale formula, per the canon, for a channel whose mapped slot is `s`:

- if **nz[s] == 1** (normalized): `scale = wb[s] * (255 - blk[s]) / 255`
- if **nz[s] == 0** (raw): `scale = wb[s]`

Then round every scale to **6 decimal places**.

**RED** — slot 2, nz[2] = 1 (normalized), so use the full formula:

```
scale_RED = wb[2] * (255 - blk[2]) / 255
          = 1.2055 * (255 - 7) / 255
          = 1.2055 * 248 / 255
          = 1.2055 * 0.97254901960784...
          = 1.17240784313725...
          -> round to 6 dp -> 1.172408
```

**GREEN** — slot 1, nz[1] = 0 (raw), so the black-level term does **not** apply;
the scale is just the white-balance gain:

```
scale_GREEN = wb[1]
            = 0.9625
            -> round to 6 dp -> 0.962500   (i.e. 0.9625)
```

Note we do *not* fold in blk[1] = 0 here. It happens to be zero anyway, so even if
you wrongly applied the normalized formula you'd get `0.9625 * (255-0)/255 =
0.9625` and not notice the bug. That's a coincidence of this example, not a license
to ignore the nz flag — on a different capture with nz=0 and a nonzero blk you'd be
wrong. Honor the flag: nz[1]=0 means raw means `scale = wb` full stop.

**NIR** — slot 0, nz[0] = 1 (normalized), full formula:

```
scale_NIR = wb[0] * (255 - blk[0]) / 255
          = 1.0840 * (255 - 12) / 255
          = 1.0840 * 243 / 255
          = 1.0840 * 0.95294117647058...
          = 1.03298823529411...
          -> round to 6 dp -> 1.032988
```

So the channel scales, in canonical RED/GREEN/NIR order:

```
RED   = 1.172408
GREEN = 0.962500
NIR   = 1.032988
```

These three numbers are the whole point of decoding the calibration block — they're
what downstream uses to normalize the three channels before inference. Get the
mapping wrong (e.g. use the superseded variant-B mapping) and RED/GREEN swap: you'd
emit RED=0.9625 and GREEN=1.172408, the image would come out color-shifted, and the
classifier's accuracy would quietly tank. This is exactly the failure the re-bench
fixed. Mapping first, then formula, then round.

### Step 8 — site registry check (unknown_site gate)

Now we resolve quarantine reason #4. The decoded site is `site-lagoon`. We check it
against the **allowed_sites** registry, which lives in `global.yaml`. For this
worked example our (fictional) `global.yaml` registry looks like:

```yaml
# global.yaml (excerpt)
allowed_sites:
  - site-lagoon
  - site-pinnacle
  - site-thermal
```

`site-lagoon` is in the list. So this capture is **not** `unknown_site`; it's
recognized. (If the decoded site had been something like `site-ghost` — a site that
isn't in `allowed_sites` — we would quarantine the capture as `unknown_site` right
here, no matter how perfect its checksum and scales were. A capture with a flawless
calibration block but an unrecognized site is still quarantined. The registry is the
gate.)

And dedup (reason #5, `superseded`): there's no other capture from `RBX-7A2C` in
this batch, so our seq=5 capture wins by default. If a sibling `RBX-7A2C` capture
with seq=6 existed, *this* one (seq 5) would be the older one and would be
quarantined as `superseded` — we keep only the highest seq per device. Not the
case here.

So this capture clears all five quarantine reasons and will be **included**.

### Step 9 — merge the model cards (precedence, with the three exceptions)

Inference settings come from three YAML layers: `global.yaml` (baseline),
`sites/<site>.yaml`, and `devices/<dev>.yaml`. Our device's site is `site-lagoon`
(the decoded field), so the site card is `sites/site-lagoon.yaml`, and the device
card is `devices/RBX-7A2C.yaml`. Fictional contents for this example:

```yaml
# global.yaml (excerpt, cont.)
model_name: reefnet-coastal
model_version: 3
input_size: [640, 640]
confidence_threshold: 0.50
labels_version: 2026.05
```

```yaml
# sites/site-lagoon.yaml
model_version: 4
input_size: [768, 768]
confidence_threshold: 0.55
```

```yaml
# devices/RBX-7A2C.yaml
model_name: reefnet-coastal-xl
input_size: [512, 512]
confidence_threshold: 0.40
```

Now resolve each field. The **default** precedence is **device > site > global**,
but it applies to **only `model_name` and `model_version`.** There are three
exceptions, and they're the whole reason this step needs a worked example.

**`model_name`** — default precedence device > site > global. Device card sets it
to `reefnet-coastal-xl`. Device wins. → **`reefnet-coastal-xl`**.

**`model_version`** — default precedence device > site > global. Device card does
*not* set `model_version` (it only overrides the name). Site card sets it to `4`.
So device is absent, fall to site: site wins over global's `3`. →
**`4`**.

**`input_size`** — **EXCEPTION**: per-site mount geometry, so precedence is
**site > global only; the device value is IGNORED.** The device card *does* set
`input_size: [512, 512]`, and it is tempting to take it because device normally
wins — **but for input_size the device is ignored entirely.** Site sets
`[768, 768]`, which beats global's `[640, 640]`. → **`[768, 768]`**. (Watch this
one: the device's `[512, 512]` is a real value sitting right there in the device
card, and it is discarded on purpose. Mount geometry is a property of the site's
physical rig, not the device.)

**`confidence_threshold`** — **EXCEPTION**: device thresholds are untrusted (a
firmware bug wrote bogus thresholds), so precedence is **site > global only; device
IGNORED.** Device card sets `0.40` — ignored. Site sets `0.55`, beating global's
`0.50`. → **`0.55`**. (Again, the device value `0.40` is present and deliberately
thrown away. Don't trust device thresholds.)

**`labels_version`** — **EXCEPTION**: centrally pinned, so for an ordinary site it is **global;
site and device are both ignored**, even if they set it (neither does here, but it
wouldn't matter). → **`2026.05`**.

So the resolved card for this device:

| field | source used | value |
|-------|-------------|-------|
| model_name | device | `reefnet-coastal-xl` |
| model_version | site (device absent) | `4` |
| input_size | site (device ignored by rule) | `[768, 768]` |
| confidence_threshold | site (device ignored by rule) | `0.55` |
| labels_version | global (pilot sites: from site card) | `2026.05` |

### Step 10 — emit the `devices[]` entry

Finally, assemble the one manifest entry this capture produces. Remember
`source_png` is the **bare** capture filename — no path prefix — and
`sensor_variant` is the raw single letter (`"A"` or `"B"`), so here it's `"B"`. The
device entries in the full manifest are sorted by `device_id`, but this is just the
one fragment:

```json
{
  "device_id": "RBX-7A2C",
  "site": "site-lagoon",
  "source_png": "rbx-7a2c-0005.png",
  "sensor_variant": "B",
  "channel_scales": {
    "RED": 1.172408,
    "GREEN": 0.9625,
    "NIR": 1.032988
  },
  "model_name": "reefnet-coastal-xl",
  "model_version": 4,
  "input_size": [768, 768],
  "confidence_threshold": 0.55,
  "labels_version": "2026.05"
}
```

That's the entire journey: base64 string → 41 raw bytes → magic/version/flags
parse with the variant and nz bit math → seq → the three /10000 white-balance floats
→ the three black levels → skip the three co debug bytes → length-prefixed
`RBX-7A2C` and `site-lagoon` → recompute CRC-16/CCITT-FALSE and confirm `0xB53A`
matches the trailer → corrected variant-B mapping (RED←slot2, GREEN←slot1,
NIR←slot0) → the nz scale formula rounded to 6 dp → site found in `allowed_sites` →
model card merged with the three precedence exceptions (device input_size and
device confidence_threshold both deliberately ignored; labels_version forced from
global) → one `devices[]` entry.

If your pipeline reproduces every intermediate number on this page — `flags=0x15`
decoding to variant B and nz=[1,0,1], wb=[1.0840, 0.9625, 1.2055], CRC `0xB53A`,
scales 1.172408 / 0.9625 / 1.032988, input_size `[768,768]`, threshold `0.55`,
labels `2026.05` — you've got the format right. If it disagrees anywhere, the
disagreement *is* the bug, and the offset where the numbers first diverge tells you
which step to go fix.
## FAQ and field gotchas

This is the page priya kept threatening to laminate. It's not a spec and it's not in order; it's the running pile of "wait, why is the manifest wrong AGAIN" questions that come up on every survey, with the short answer first and the war story second. New folks: read the whole thing once on the boat ride out, then come back and skim the bold lines when something breaks. Old folks: yes, some of this contradicts what you were told in 2024. Trust the later errata, not the cheat-sheet. That's the whole house style of this notebook.

Format is deliberately scattered because the mistakes are scattered. I'm not going to give you one tidy table that hands you the entire decoder, because then you'll copy the table, get one row wrong, and never understand *why* it's wrong. You'll understand why here.

---

**Q: I opened the `tEXt` chunk and the value is just a long string. Can I read the device id straight out of it?**

No. God, no. The value *looks* like text because it's base64, and base64 is always printable ASCII — letters, digits, `+`, `/`, maybe an `=` or two on the end. That printability is exactly the trap. Decode the base64 first. What you get back is **not** a string. It is a packed **binary** blob. Raw bytes. There is no human-readable device id sitting in the chunk value; the device id is buried inside the binary, length-prefixed, after a bunch of integer fields. If you `grep` the chunk value for your camera's name you will find nothing and conclude the calibration is missing, which it isn't, and then you'll quarantine a perfectly good capture for `missing_calibration` when the real story is "you forgot to base64-decode." Decode, *then* parse bytes. Say it with me: base64 of packed binary, not text.

This burned an entire survey day once (see INC-2207). It is the single most common first mistake and it costs the most hours, because the symptom — "I see a string, I'll parse the string" — feels so reasonable.

---

**Q: Fine, I decoded the base64. The first two bytes are `0x52 0x42`. Is that meaningful or noise?**

Meaningful. `0x52 0x42` is ASCII `"RB"`. That's the magic. Every valid ReefBox calibration block starts with those two bytes. If the first two bytes after base64-decode are anything else, the block is corrupt or you decoded the wrong thing, and the capture is `bad_checksum` (more on that distinction below — magic failures land in the same bucket as CRC failures). Byte 2 after the magic is the version: `0x01` legacy 1.x, `0x02` modern 2.x. The byte layout is *identical* between the two versions — don't go looking for a different parser for v1, there isn't one. Version just tells you which firmware generation wrote it; it does not change how you read the bytes.

---

**Q: The integers look insane. A white-balance value came out as something like 41984. Did I corrupt the blob?**

Almost certainly you read it **little-endian**. Everything multi-byte in this format is **big-endian**. Most significant byte first. The blob came off a camera, and the camera people picked network byte order, and they were right to, and it has tripped up every single person who writes their first decoder on a little-endian laptop and forgets.

Concrete: suppose `wb[0]` occupies bytes `0x28 0xCD`. Big-endian that's `0x28CD` = 10445. Little-endian you'd read `0xCD28` = 52520, which is garbage. The fixed-point math (next question) only works out to a sane float if you read big-endian. So when a `wb` comes out as 41984 or 52520 or some other wild number, your first hypothesis is *not* "the blob is bad," it's "I read the bytes backwards." Check endianness before you check anything else.

This applies to *every* multi-byte field: `seq` (uint16), all three `wb` values (uint16 each), and the trailing `crc16` (uint16). The single-byte fields — version, flags, the three `blk` bytes, the three `co` bytes, the two length prefixes — obviously have no endianness, but the moment a field is two bytes wide, it's big-endian. No exceptions in this format.

---

**Q: I divided the white-balance by 1000 and my scales are 10x too big. What gives?**

`wb` is fixed-point over **10000**, not 1000. The stored value is `round(wb * 10000)`, so to recover the float you divide the stored uint16 by **10000.0**. A stored `10445` is `1.0445`, not `10.445`. If your channel scales are coming out roughly an order of magnitude too large (or too small if you went the other way), this `/1000` vs `/10000` slip is the usual culprit. It's an easy typo to make and an easy one to miss because the result is still a "plausible-ish" number — `10.445` doesn't scream "wrong" the way a negative or a NaN would. Count the zeros. Four of them.

While we're here: the three `blk` bytes (block / black-level) are plain uint8s in the range 0..15. They are not fixed-point, you don't divide them, they're just small integers. Don't apply the /10000 to those by reflex.

---

**Q: How do I verify my decoder before I trust it on real captures?**

CRC self-test. The trailer is the part everyone gets wrong, so prove your CRC implementation against a known answer before you point it at the fleet. The trailer is **CRC-16/CCITT-FALSE**: polynomial `0x1021`, init `0xFFFF`, no input reflection, no output reflection, final XOR `0x0000`. The canonical check value for that exact CRC over the ASCII string `"123456789"` is **`0x29B1`**. If you run your CRC over the nine bytes `31 32 33 34 35 36 37 38 39` and get `0x29B1`, your CRC is correct. If you get anything else, fix the CRC before you go further — every capture will quarantine as `bad_checksum` and you'll think the cameras are broken when it's your polynomial.

I cannot stress the self-test enough. We've had three separate people independently implement "a CRC-16" that wasn't *this* CRC-16 — wrong init value, or they turned on reflection because some library defaulted to it, or they used a final XOR of `0xFFFF`. All three produced confident, wrong, stable answers, and all three failed the `0x29B1` check immediately. Two minutes of self-test saves you a survey.

---

**Q: I'm using a byte sum / a simple checksum for the trailer and it never matches. Is the camera writing the CRC wrong?**

The camera is fine; you're computing the wrong thing. The trailer is **not** a byte sum, not an XOR-of-bytes, not an Adler, not a CRC32 truncated to 16 bits. It is specifically CRC-16/CCITT-FALSE as described above, computed over **every preceding byte** in the block — magic, version, flags, seq, all the wb/blk/co bytes, the length prefixes, the device id ASCII, the site id ASCII — everything up to but not including the two trailer bytes themselves. Then you compare your computed value to the uint16 you read (big-endian!) from the last two bytes. Match → block integrity is good. Mismatch → `bad_checksum`, quarantine it, the capture is corrupt or truncated.

A byte sum will *coincidentally* match maybe never, so if you're getting "never matches," that's consistent with "wrong algorithm entirely," which points right back at "it's a CRC, not a sum." Run the `0x29B1` self-test.

---

**Q: There are three bytes I can't figure out what they're for — `co[0] co[1] co[2]`, right after the blk bytes. What channel order do they encode?**

None that you should ever use. Those three bytes are the **`co` debug triple** — a leftover channel-order hint the firmware writes for the bench team's diagnostics. **Skip them. Never use them.** The channel mapping is decided by the sensor variant in the flags byte and *only* by the variant. The `co` triple lies often enough (it reflects a debug build's internal ordering, not the shipped optics) that we condemned it outright. Read past it, throw it away, move on.

But — and this is the gotcha inside the gotcha — **you still have to count them.** They occupy bytes 15, 16, 17. If you "skip" them by simply not reading them but also not advancing your byte cursor past them, every field after them is misaligned by three bytes. The very next byte (18) is `dev_len`, the length of the device id. Miscount the `co` skip and you read `dev_len` from the wrong byte, which means you read a wrong length, which means you slice a wrong number of bytes for the device id, which throws off `site_len`, which throws off the site id, which throws off where the CRC trailer starts — and now your CRC fails and you blame the camera. One misplaced cursor and the whole tail of the blob shreds.

So: skip `co` *semantically* (never feed it into channel logic), but advance the cursor *exactly three bytes* past it. Ignore the values, honor the offsets.

---

**Q: Variant B is just straight-through with the colors swapped a little, right? RED from slot1?**

No, and this is the correction that's bitten the most people because the *old* note said exactly that. Let me be very precise, because there are two layers of wrong here.

Variant A is straight-through: slot0→RED, slot1→GREEN, slot2→NIR. Easy. That's the one people over-generalize from.

Variant B is the cost-down board and it is **not** straight-through. The current, re-benched, authoritative mapping is:

- **RED comes from slot2**
- **GREEN comes from slot1**
- **NIR comes from slot0**

slot1→GREEN happens to stay put, which is why people misremember B as "almost A." It isn't. The two *visible* channels are transposed relative to a naive read, and NIR and RED swap ends.

Here's the part that makes people distrust the page: an earlier note had Variant B as RED-from-slot1 / GREEN-from-slot2. **That earlier note is superseded and wrong.** The re-bench transposed the two visible channels and corrected it. RED is **slot2**. GREEN is **slot1**. If you're reading an old printout that says RED-from-slot1, set it on fire. The canonical output order is always RED, GREEN, NIR regardless of variant — what changes per variant is which stored slot *feeds* each of those output channels, and for B it's RED←slot2, GREEN←slot1, NIR←slot0.

Worked sanity check on a fictional unit, RBX-7A2C, decoded as Variant B with stored slots `[wb0, wb1, wb2]`: the RED channel scale is computed from slot **2**'s wb/blk/nz, GREEN from slot **1**, NIR from slot **0**. If you computed RED off slot0, you ran it as if it were Variant A, and your red channel is now your NIR channel, and your reef looks like it's on fire in infrared. Not great.

---

**Q: And Variant C?**

Variant C is the defective-lens batch. Captures from it are **unusable**. Don't try to map channels, don't try to salvage scales — quarantine the capture with reason `sensor_variant_c` and move on. There is no recovery path. The flags byte's low two bits give you the variant (0=A, 1=B, 2=C); if it decodes to 2, you're done with that capture.

---

**Q: How exactly do I turn a slot's stored values into a channel scale?**

For a given canonical channel, first find its mapped stored slot `s` (via the variant rules above — A straight-through, B is RED←2/GREEN←1/NIR←0, C unusable). Then look at that slot's normalization flag `nz[s]`:

- If `nz[s] == 1` (normalized): `scale = wb[s] * (255 - blk[s]) / 255`
- If `nz[s] == 0` (raw): `scale = wb[s]`

Then **round to 6 decimal places.** Every scale, six decimals, no exceptions. Not 4, not "however many Python prints," six.

The `nz` flags live in the flags byte: bit 2 is `nz[0]`, bit 3 is `nz[1]`, bit 4 is `nz[2]`. (Bits 0–1 are the variant, as above.) So one byte carries both the variant and the three normalization flags; don't read `nz` from somewhere else, there is nowhere else. Common slip: applying the normalized formula to a raw channel because you read the wrong bit. If a channel's scale equals its raw `wb` exactly and you expected the `(255-blk)/255` knockdown, check which `nz` bit you grabbed.

The rounding matters more than it looks. We diff manifests against an expected output, and an unrounded `1.0444999999998` vs the expected `1.0445` is a failed diff even though the numbers are "the same." Round at the point of emission, six places.

---

**Q: Two cards came off the camera and I've got two PNGs from the same device. Do I keep both?**

No. **Highest `seq` wins, per device.** The `seq` field (bytes 4–5, uint16, big-endian — yes, big-endian, see above) is the sequence number. When two or more captures decode to the same device id, you keep **only** the one with the highest `seq`, and every older same-device capture is quarantined with reason `superseded`. Not dropped silently — quarantined, with a reason, so it shows up in the manifest's quarantined list and someone can audit it later.

Gotcha: the dedup is on the **decoded** device id, not the filename. `rbx-7a2c-0001.png` and `rbx-7a2c-0007.png` might be the same physical camera, or the filenames might lie entirely. Decode the device id out of the binary and dedup on *that*. Two files with totally different names can be the same device; one device's captures can have wildly non-contiguous seqs. Trust the decoded `dev`, never the filename stem.

---

**Q: What's the difference between `bad_checksum` and `missing_calibration`? They both feel like "the calibration is broken."**

They are not the same and the order you check them in matters.

- **`missing_calibration`** means **neither** calibration key is present in the PNG at all. No `reefbox:calibration` chunk, no `rbx:cal` chunk. There is nothing to decode. The camera never wrote calibration, or someone stripped the metadata (the classic: an image tool "optimized" the PNG and silently dropped ancillary `tEXt` chunks). Empty-handed.

- **`bad_checksum`** means a calibration block **is** present, but it won't decode or it fails integrity: wrong magic, can't be parsed, or the recomputed CRC doesn't match the trailer (corrupt or truncated). You *have* bytes; the bytes are bad.

So: nothing there → `missing_calibration`. Something there but broken → `bad_checksum`. Don't conflate them; the reason token you emit has to be the right one or the audit downstream points at the wrong failure mode.

---

**Q: Both `reefbox:calibration` AND `rbx:cal` are present on the same PNG. Which do I read?**

`reefbox:calibration` wins. That's the 2.x modern key and it's authoritative. `rbx:cal` is the legacy 1.x key and it's fallback-only. The double-key situation is a known bad batch — a "double-write" run of 2.x units that left *both* keys on the image. When both are present, read the **`reefbox:calibration`** block and ignore the leftover `rbx:cal` entirely. Don't try to reconcile them, don't average them, don't prefer the one that "looks healthier." 2.x present → use 2.x, full stop. Only fall back to `rbx:cal` when `reefbox:calibration` is genuinely absent. Neither present → `missing_calibration`.

---

**Q: A capture decoded fine, channels mapped, scales computed — but the site it decoded to is `site-ghost` and I've never heard of it. Now what?**

Check it against the **site registry**. `global.yaml` carries an `allowed_sites` list — that's the registry of recognized sites. The device's site is whatever the calibration block decoded as the site field (not what an operator typed on a clipboard). If that decoded site is **not** in `allowed_sites`, quarantine the capture with reason `unknown_site`. `site-ghost` is exactly the kind of thing you'll see when a camera was bench-tested with a placeholder site id and shipped without re-flashing — it decodes cleanly, the CRC is fine, the optics are fine, but the site is bogus and we won't run inference for a site we don't have a model card for.

This is *not* a calibration failure, which is why it's checked later in the order (below). The block is perfectly valid. The site is just unrecognized.

---

**Q: A single capture seems to qualify for two quarantine reasons. Which one do I report?**

Exactly one reason per capture, and there's a strict order. Evaluate **in this order, first match wins**:

1. `missing_calibration`
2. `bad_checksum`
3. `sensor_variant_c`
4. `unknown_site`
5. `superseded`

So if a capture has no calibration at all, it's `missing_calibration` and you never even get far enough to notice it would also have been superseded. If it decodes but is Variant C *and* from an unknown site, it's `sensor_variant_c` because that's earlier in the order. You don't list two reasons, you don't pick the "worst" one — you walk the list top to bottom and stop at the first that applies. Five tokens, that order, period.

The logic of the order, if it helps you remember: you can't check the site or the seq of a capture you couldn't even decode, so the decode-level failures (`missing_calibration`, `bad_checksum`) come first; then the variant (which you only know *after* decode); then the semantic checks (`unknown_site`, then `superseded`) that assume a good decode. It's roughly "can I parse it → can I use this sensor → is this a real site → is this the freshest copy."

---

**Q: In the final manifest, how do I sort things, and what filename do I put in `source_png`?**

Two different sort keys, don't mix them up:

- The **devices** array (the included captures) is sorted by **`device_id`**.
- The **quarantined** array is sorted by **`source_png`**.

And `source_png` is the **bare capture filename** — `rbx-7a2c-0005.png` — never path-prefixed. No `./captures/`, no absolute path, no directory at all. Just the filename. We've shipped manifests with `survey7/rbx-7a2c-0005.png` in the field and the downstream tool either can't find the file or sorts it wrong because the path prefix throws off the ordering. Strip to the basename.

People mix these two up constantly: they sort everything by `source_png`, or everything by `device_id`. It's devices-by-device_id, quarantined-by-source_png. Different arrays, different keys.

---

**Q: What goes in the `sensor_variant` field of the manifest — the number, the variant name, what?**

The **bare single letter**. `"A"` or `"B"`. Not `0`/`1`, not `"Variant B"`, not `"variant_b"` — just the uppercase letter. (You won't be emitting `"C"` in an *included* device, because Variant C captures get quarantined as `sensor_variant_c` and never make it into the devices array.) So the flags low-two-bits decode to a number 0/1/2 internally, but what lands in the manifest is the letter `A`/`B`.

---

**Q: While I'm in the YAML — device card has a `confidence_threshold`, an `input_size`, and a `labels_version`. Default rule is device beats site beats global, so device wins all three?**

No. There are **three exceptions** to "device > site > global," and they exist because of real incidents (see PM-4471 and the labels-pin errata). The default precedence applies to **`model_name` and `model_version` only**. For the other three fields:

- **`confidence_threshold`**: device thresholds are untrusted (firmware bug wrote garbage into auto-stamped device cards). Resolves **site > global only**. Device card's threshold is ignored, always — even if it looks like a reasonable number. A plausible-but-wrong `0.31` is indistinguishable from a real one, so we condemned the whole device source for this field.
- **`input_size`**: this is per-site **mount geometry** (lens, port window, housing crop), not a per-device choice. Resolves **site > global only**. Device card's `input_size` is ignored. A re-housed camera carries a stale device `input_size` from its previous posting; the site is the truth.
- **`labels_version`**: centrally pinned. **Global for ordinary sites; pilot sites take it from the site card (see the label memo carve-out).** Site and device otherwise ignored. We pin labels fleet-wide so every capture is scored against the same label set; letting a site or device drift the label version silently breaks comparability across the survey.

So for those three: threshold and input_size are `site > global` (device dropped), labels_version is `global` only for ordinary sites (site and device both dropped; pilot sites — currently `site-alpha` — take it from the site card, per the label memo's 2026-03-18 carve-out). Only `model_name`/`model_version` get the full `device > site > global`. Memorize the exceptions, not the default — the default is the easy part.

---

**Q: Quick gut-check list before I trust a manifest?**

Run down this, field-voiced, in order:

- Did I **base64-decode** the chunk value before parsing? (Not parsing it as text.)
- Am I reading multi-byte fields **big-endian**?
- Did I divide `wb` by **10000**, not 1000?
- Does my CRC pass the **`0x29B1`** self-test on `"123456789"`, and is it CRC-16/CCITT-FALSE (poly `0x1021`, init `0xFFFF`, no reflection, XOR-out `0x0000`)?
- Did I **skip the three `co` bytes** for channel logic but still **advance the cursor** past them so `dev_len` and everything after lines up?
- For Variant B, is RED coming from **slot2** and GREEN from **slot1** (NIR from slot0)? Not the old slot1-RED note.
- Did I apply the right `nz`-based scale formula per slot, and **round to 6 decimals**?
- Did I dedup same-device captures keeping the **highest seq** (and quarantine the rest as `superseded`)?
- Did I check decoded site against `allowed_sites` and emit `unknown_site` if it's not registered?
- Did I evaluate the **five** quarantine reasons in order — `missing_calibration`, `bad_checksum`, `sensor_variant_c`, `unknown_site`, `superseded` — one reason per capture?
- Devices sorted by **device_id**, quarantined sorted by **source_png**, `source_png` is the **bare filename**, `sensor_variant` is the **bare letter**?
- Did I respect the **three precedence exceptions** — confidence_threshold (site>global), input_size (site>global), labels_version (global for ordinary sites; pilot sites like `site-alpha` from the site card) — and let only model_name/model_version use device>site>global?

If every one of those is a yes, the manifest is probably right. If it's wrong anyway, it's almost always one of the first four — they're the ones that produce confident, plausible, *wrong* output instead of an obvious crash. The crashes are easy. It's the plausible wrong answers that lose surveys.
## Appendix: byte layout, manifest shape, change log, and sign-off

This is the back-of-the-book section. If you only ever read one part of this notebook, you probably read section 1 (the welcome) and then jumped here looking for the byte table, because that's what everyone does. That's fine. But please read the change log at the bottom before you trust anything above it — half of what got written in year one was wrong, and the corrections are scattered across a dozen errata and postmortems. The whole point of this appendix is to gather the *current* truth in one place so you stop grepping the journal at 2am on a boat.

Reminder of the reading convention, because it governs everything here too: this notebook is append-mostly and roughly chronological. When a later dated ERRATA or postmortem contradicts earlier text, **the later entry wins**. Trust the errata, not the cheat-sheet. This appendix is itself a "later entry" relative to most of the book, so where it disagrees with something you read earlier, this appendix is more likely current — but if you find a *dated* errata newer than this appendix, that errata wins over this appendix. We're not above our own rule.

### A.1 — The calibration block: where it lives

Every ReefBox capture is a PNG, and the calibration travels *inside* the PNG as a `tEXt` chunk. There are two metadata keys you might find:

- `reefbox:calibration` — firmware 2.x, the modern block. **Authoritative.**
- `rbx:cal` — legacy 1.x, the old block. **Fallback only.**

If both keys are present (yes, this happens — the "double-write" batch of 2.x units left both, see the change log), the **`reefbox:calibration` (2.x) block wins** and the leftover `rbx:cal` block is ignored. You do not merge them, you do not average them, you do not look at the legacy one "just to check." You take the 2.x one and move on. If neither key is present, the capture is `missing_calibration` and gets quarantined — there's nothing to decode.

The chunk's **value is not text you can read**. It is **base64**, and what it encodes is a **packed binary blob**. So the pipeline is always: pull the chunk value out of the PNG → base64-decode it → parse the resulting *bytes* per the table below. People keep trying to "read" the value and concluding the camera is broken because it looks like line noise. It's base64. Decode it first.

### A.2 — Byte layout reference (the table everyone wants)

All multi-byte integers are **big-endian**. No exceptions. The byte layout is **identical for version 1 and version 2** — the only thing the version byte changes is which *key* the block came from, not how you parse it.

| Offset | Size | Field | Type | Notes |
|-------:|-----:|-------|------|-------|
| 0–1 | 2 | magic | ASCII | the two bytes `"RB"` = `0x52 0x42`. Wrong magic → can't parse → `bad_checksum`. |
| 2 | 1 | version | uint8 | `1` = legacy, `2` = modern. Layout identical either way. |
| 3 | 1 | flags | uint8 | bit-packed; see A.3. |
| 4–5 | 2 | seq | uint16 (BE) | capture sequence number; drives dedup. |
| 6–7 | 2 | wb[0] | uint16 (BE) | fixed-point: stored value = `round(wb * 10000)`; divide by 10000 to recover the float. |
| 8–9 | 2 | wb[1] | uint16 (BE) | same /10000 convention. |
| 10–11 | 2 | wb[2] | uint16 (BE) | same /10000 convention. |
| 12 | 1 | blk[0] | uint8 | black level, 0..15. |
| 13 | 1 | blk[1] | uint8 | black level, 0..15. |
| 14 | 1 | blk[2] | uint8 | black level, 0..15. |
| 15 | 1 | co[0] | uint8 | **DEBUG channel-order triple. IGNORE.** |
| 16 | 1 | co[1] | uint8 | **IGNORE.** |
| 17 | 1 | co[2] | uint8 | **IGNORE.** |
| 18 | 1 | dev_len | uint8 | length of the device id that follows. |
| 19 … | dev_len | device id | ASCII | exactly `dev_len` bytes. |
| next | 1 | site_len | uint8 | length of the site id that follows. |
| next … | site_len | site id | ASCII | exactly `site_len` bytes. |
| last 2 | 2 | crc16 | uint16 (BE) | CRC-16/CCITT-FALSE over **every preceding byte**. See A.4. |

The two variable-length fields (`device id`, `site id`) are why you can't hard-code offsets past byte 17. Read `dev_len`, consume that many bytes, *then* read `site_len`, consume that many, *then* the last two bytes are the CRC. A surprising number of "corrupt block" reports were actually someone assuming a fixed 8-byte device id.

A practical reading note: validate the total length as you go. After you've consumed `dev_len` device bytes and `site_len` site bytes, there should be **exactly two** bytes left for the CRC. If there are fewer than two, the blob was truncated — that's `bad_checksum`, not a parsing edge case to paper over. If there are *more* than two left over, you mis-read one of the length prefixes (almost always because you read it as the wrong width or off by one), so back up and check your cursor. The length-prefixed layout is self-describing on purpose: a correctly parsed block lands its cursor exactly on the last byte of the CRC with nothing dangling. Treat "leftover bytes" as a loud signal that your parser is wrong, not the data.

One more: the device id and site id are **ASCII**, not UTF-8 with surprises and not null-terminated. The length prefix is the only thing that tells you where each string ends. Do not look for a `0x00` terminator; there isn't one, and if you stop at the first zero byte inside what you *think* is a string, you've desynced and the rest of the parse is garbage. Consume exactly `dev_len` / `site_len` bytes, no more, no less.

#### The co bytes again, because someone always uses them

Bytes 15, 16, 17 are the **co** triple — a leftover *debug* channel-order hint from the bring-up tooling. **Skip them. Never use them.** Channel mapping is decided **only** by the sensor variant in the flags byte (A.3). The co bytes are not authoritative, they were never authoritative, and they are frequently stale relative to the actual board. If you ever find yourself routing RED/GREEN/NIR based on co, stop, back out, and use the variant. This is in the change log too because it bit us hard once.

### A.3 — The flags byte (offset 3), bit by bit

One byte, packed. Number bits from the LSB:

```
 bit:   7   6   5   4    3    2    1   0
        -   -   - nz[2] nz[1] nz[0]  variant(2 bits)
```

- **Bits 0–1** = sensor variant. `0` → A, `1` → B, `2` → C. (Bit0 + bit1 read together as a little 2-bit number.)
- **Bit 2** = `nz[0]` (normalization flag for stored slot 0).
- **Bit 3** = `nz[1]`.
- **Bit 4** = `nz[2]`.
- Bits 5–7: reserved / unused right now. Don't assume they're zero, just don't read meaning into them.

So if flags = `0b00011001` = `0x19`: variant = `01` = **B**; nz[0] = bit2 = 0; nz[1] = bit3 = 1; nz[2] = bit4 = 1. Three little flags and a variant, all in one byte.

#### Variant → channel mapping (this is the part people get wrong)

Canonical output order is always **RED, GREEN, NIR**. The **variant alone** decides which stored slot feeds each canonical channel. Never use co.

- **Variant A** — straight through: `slot0 = RED`, `slot1 = GREEN`, `slot2 = NIR`.
- **Variant B** — the cost-down board. **TRUE mapping (latest re-bench):** `slot0 = NIR`, `slot1 = GREEN`, `slot2 = RED`. So **RED comes from slot2, GREEN from slot1, NIR from slot0.** An earlier note (now superseded) had RED at slot1 and GREEN at slot2 — that was wrong; the re-bench found the two *visible* channels were transposed. RED is slot2. GREEN is slot1. Burn it in.
- **Variant C** — defective lens batch. Captures are **unusable**. Quarantine as `sensor_variant_c`. Don't try to salvage them.

### A.4 — The CRC trailer

The last two bytes of the blob are a **CRC-16/CCITT-FALSE** over **every byte that precedes them** (magic through the end of the site id, inclusive). Parameters:

- Polynomial: `0x1021`
- Init: `0xFFFF`
- **No** input reflection, **no** output reflection
- Final XOR: `0x0000`

**Check value:** the CRC of the ASCII string `"123456789"` is **`0x29B1`**. Run that through your implementation first. If you don't get `0x29B1`, your CRC is wrong and nothing downstream will agree with the reference manifest — fix the CRC before debugging anything else.

If the recomputed CRC over the preceding bytes does **not** equal the stored trailer, the capture is corrupt or truncated and goes to `bad_checksum`. Same bucket if the magic is wrong or the block otherwise refuses to parse. Integrity failures are not warnings — they remove the capture from inference.

#### Tiny worked hex dump (fictional)

A small Variant A, version 2 blob for a made-up device. This is illustrative; the trailer here is a placeholder, not a real CRC:

```
52 42 02 04  00 05  27 10 23 28 1E 14  02 01 00  06 06 06  ...
^^^^^ ^^ ^^  ^^^^^  -----wb x3------  blk x3   --co skip--
"RB"  v2 fl  seq=5

flags 0x04 = 0b00000100 -> variant 00=A, nz[0]=1, nz[1]=0, nz[2]=0
wb[0]=0x2710=10000 -> 1.0000   wb[1]=0x2328=9000 -> 0.9000   wb[2]=0x1E14=7700 -> 0.7700
blk = [2,1,0]    co = [6,6,6] (IGNORED)
```

…then `dev_len`, the device-id bytes, `site_len`, the site-id bytes, and finally the 2-byte CRC over everything above. Note the `co` triple `06 06 06` sitting there looking meaningful — and we walk right past it.

### A.5 — Per-channel scale

For each canonical channel, find its mapped stored slot `s` (via the variant), then:

- if `nz[s] == 1` (normalized): `scale = wb[s] * (255 - blk[s]) / 255`
- if `nz[s] == 0` (raw): `scale = wb[s]`

**Round every scale to 6 decimal places.** The rounding is part of the contract — the reference manifest is rounded to 6dp and a byte-for-byte comparison will fail if you emit full float precision.

Worked example, Variant B, using the blob fields above but pretending it were variant B (so RED←slot2, GREEN←slot1, NIR←slot0) and nz = [1,1,0]:

- RED uses slot2: nz[2]=0 → raw → scale = wb[2] = 0.770000
- GREEN uses slot1: nz[1]=1 → normalized → scale = wb[1] * (255 - blk[1]) / 255 = 0.9000 * (255-1)/255 = 0.896471
- NIR uses slot0: nz[0]=1 → normalized → scale = wb[0] * (255 - blk[0]) / 255 = 1.0000 * (255-2)/255 = 0.992157

The slot is chosen by the variant; the nz flag and blk value are *indexed by the slot*, not by the canonical channel. That distinction — "look up nz and blk by the slot you mapped to, not by RED/GREEN/NIR position" — trips people on Variant B specifically, because the mapping is shuffled.

The cleanest way to keep it straight in code: build the variant's slot map first as a little lookup — for A it's `{RED:0, GREEN:1, NIR:2}`, for B it's `{RED:2, GREEN:1, NIR:0}` — then for each canonical channel do `s = slotmap[channel]` and pull `wb[s]`, `nz[s]`, `blk[s]` all by the same `s`. Don't ever pull `wb` by the channel index and `nz` by the slot index, or vice versa; both come from `s`. On Variant A the two happen to coincide so the bug hides; on Variant B it surfaces immediately as swapped RED/NIR. We've seen exactly this — a decoder that worked perfectly on the variant-A test fixtures and then mislabeled every cost-down board in production because it indexed `nz` by channel. Test on a Variant B fixture *specifically*, or you won't catch it.

And to say it once more so nobody has to scroll: the scale rounds to **6 decimal places**. Not 4, not "however many Python feels like printing," six. The comparison against the reference manifest is exact text, and `0.896471` is not `0.8964705882`.

### A.6 — Deduplication

Two or more captures can carry the same `dev`. Keep **only** the one with the **highest `seq`**. Every older same-dev capture is quarantined as `superseded`. Dedup is by decoded device id, not by filename, not by site. If three captures from `RBX-7A2C` show up with seq 3, 7, and 12, you keep seq 12 and quarantine the other two as `superseded`.

### A.7 — Inference settings & the precedence rules

Inference settings come from YAML, layered:

- `global.yaml` — baseline.
- `sites/<site>.yaml` — per-site.
- `devices/<dev>.yaml` — per-device.

A device's site is the **decoded site field** from the calibration block. `global.yaml` also carries an **`allowed_sites`** list — that's the registry of recognized sites.

**Default precedence is device > site > global**, but it applies to **only** `model_name` and `model_version`. Then there are exactly **three exceptions** — restating them here because this is the page people screenshot:

1. **`input_size`** — per-site mount geometry. Precedence is **site > global only**; the device value is **ignored**. (The lens/housing geometry is a property of the mount at the site, not the camera body.)
2. **`confidence_threshold`** — device-supplied thresholds are **untrusted** (firmware bug wrote garbage). Precedence is **site > global only**; the device value is **ignored**.
3. **`labels_version`** — centrally pinned. **Global for ordinary sites; pilot-site devices take it from their site card (see the label memo carve-out).** Site and device otherwise **ignored**.

For everything not named above, the default device > site > global stands; in practice that's just `model_name` and `model_version`.

### A.8 — The five quarantine reason codes (and their order)

Never drop a capture silently. There are exactly **five** reason-code tokens, and you evaluate them **in this order**, first match wins, **exactly one reason per capture**:

1. `missing_calibration` — neither calibration key present.
2. `bad_checksum` — a block is present but won't decode / its CRC fails (corrupt or truncated, bad magic, etc.).
3. `sensor_variant_c` — sensor variant C.
4. `unknown_site` — decoded site is not in `global.yaml` `allowed_sites`.
5. `superseded` — lost the same-device dedup (older seq).

Order matters because a single capture can trip more than one rule. A truncated blob from a Variant C camera at an unrecognized site is `bad_checksum` — not `sensor_variant_c`, not `unknown_site` — because `bad_checksum` comes first and you can't even trust the variant or site bytes out of a block that failed its CRC. Walk the list top to bottom and stop at the first hit.

### A.9 — Manifest shape (small fragment)

The downstream manifest is JSON. Top-level: `manifest_version` `"1.0"`; `channel_order` is always `["RED","GREEN","NIR"]`; `devices` is an array **sorted by `device_id`**; `quarantined` is an array **sorted by `source_png`**; `summary` is `{included, quarantined}`. Each device entry carries `device_id`, `site`, `source_png`, `sensor_variant`, `channel_scales` `{RED, GREEN, NIR}` rounded to 6dp, `model_name`, `model_version`, `input_size` `[w, h]`, `confidence_threshold`, `labels_version`.

Two things people get wrong on output:

- **`source_png` is the BARE capture filename** — e.g. `"rbx-7a2c-0005.png"` — never path-prefixed. Strip directories.
- **`sensor_variant` is the raw single letter** — `"A"` or `"B"`. (You'll never emit `"C"`; those are quarantined.)

A small fictional fragment — **one** included device and **one** quarantined entry — just to anchor the shape:

```json
{
  "manifest_version": "1.0",
  "channel_order": ["RED", "GREEN", "NIR"],
  "devices": [
    {
      "device_id": "RBX-7A2C",
      "site": "site-lagoon",
      "source_png": "rbx-7a2c-0012.png",
      "sensor_variant": "B",
      "channel_scales": {
        "RED": 0.770000,
        "GREEN": 0.896471,
        "NIR": 0.992157
      },
      "model_name": "reefnet-coastal",
      "model_version": "3.2.1",
      "input_size": [640, 640],
      "confidence_threshold": 0.45,
      "labels_version": "labels-2026-04"
    }
  ],
  "quarantined": [
    {
      "source_png": "rbx-22e9-0003.png",
      "reason": "bad_checksum"
    }
  ],
  "summary": {
    "included": 1,
    "quarantined": 1
  }
}
```

Notice: `source_png` values are bare filenames; `sensor_variant` is `"B"` not `"Variant B"`; scales carry six decimals; the quarantined entry is just `{source_png, reason}` with one of the five tokens; `labels_version` is the global-pinned value regardless of what `devices/RBX-7A2C.yaml` might say. (`input_size` `[640, 640]` here came from `sites/site-lagoon.yaml`, not from the device — exception 1.)

### A.10 — Change log (read this)

This is the spine of the whole notebook: the dated corrections, newest-supersedes-oldest. Each line below points at the originating errata/postmortem so you can go read the war story. If any entry here disagrees with body text earlier in the notebook, the entry here (and the dated source it cites) wins.

- **ERRATA-002 — "the value is base64 of binary, not text."** Early onboarding text described the chunk value as a text spec. Wrong. The value is base64; decode it, then parse the **packed binary** blob. This errata is the reason A.1 exists. Everything that treated the value as readable text is superseded.

- **ERRATA-004 — "everything multi-byte is big-endian."** Bring-up notes were ambiguous and at least one early decoder read `seq` and `wb` little-endian, producing garbage scales that *looked* plausible enough to ship. All multi-byte integers — `seq`, the three `wb`, the CRC — are **big-endian**. Supersedes any little-endian reading.

- **ERRATA-006 — "wb is fixed-point /10000."** The `wb` slots are `uint16` fixed-point: stored = `round(wb * 10000)`, recover by dividing by 10000. An early draft treated them as raw integers (so 1.0 looked like 10000 in a scale and nobody could figure out why thresholds were off by 4 orders of magnitude). Supersedes the raw-integer reading.

- **PM-011 — CRC adoption / `bad_checksum`.** Postmortem after a run shipped on a truncated blob and quietly produced nonsense channels for a whole site-week. Outcome: enforce the **CRC-16/CCITT-FALSE** trailer (poly `0x1021`, init `0xFFFF`, no reflection, final XOR `0x0000`, check `0x29B1`) and add the `bad_checksum` quarantine bucket. Before this, integrity failures were silently included. Supersedes "if it decodes at all, use it."

- **PM-013 — the `co` debug triple is not the channel order.** This is the painful one. Someone wired channel mapping off the `co` bytes (15–17) because they looked like a channel order and the field was even named "channel order." On the cost-down boards the `co` triple was stale and we mislabeled NIR as RED for an entire deployment. Resolution: **ignore `co` entirely; the variant in the flags byte alone decides mapping.** Supersedes any code path that reads `co`.

- **ERRATA-009 — Variant B re-bench (the transpose).** The original Variant B mapping in the notebook had **RED at slot1, GREEN at slot2**. A later bench re-test found the two visible channels were swapped on the actual silicon. **Corrected, current mapping: RED ← slot2, GREEN ← slot1, NIR ← slot0.** This errata supersedes the earlier Variant B note. If you see RED-at-slot1 anywhere in the body text, it's the old, wrong version.

- **ERRATA-012 — the double-write batch / key precedence.** A bad batch of 2.x units wrote **both** `reefbox:calibration` (2.x) and `rbx:cal` (1.x) keys into the same PNG. Rule clarified: when both keys are present, the **2.x `reefbox:calibration` block wins** and the legacy `rbx:cal` block is **ignored**. Neither present → `missing_calibration`. Supersedes any "prefer legacy" or "merge both" guidance.

- **ERRATA-014 — `input_size` pulled out of default precedence.** `input_size` reflects per-site **mount geometry**, so a device's `input_size` is meaningless and was occasionally wrong. Rule: `input_size` is **site > global only; device ignored.** This pulled `input_size` out of the default device > site > global path. Supersedes any manifest that took `input_size` from a device YAML.

- **ERRATA-015 — `confidence_threshold` device value untrusted.** A firmware bug wrote bogus `confidence_threshold` values into device YAMLs. Rule: **site > global only; device ignored** for `confidence_threshold`. Supersedes any precedence that let the device set the threshold.

- **ERRATA-016 — `labels_version` centrally pinned.** Label sets must be uniform across the whole fleet for comparability. Rule: `labels_version` is **global for ordinary sites**; site and device otherwise ignored. Later refined by the 2026-03-18 pilot carve-out, under which a pilot-site device (currently `site-alpha`) takes `labels_version` from its site card.

- **PM-018 — site registry / `unknown_site`.** We ingested captures from a site that was never provisioned (decoded site `site-ghost`) and there was no model card for it, so the pipeline fell back to global silently and produced uncomparable results. Resolution: `global.yaml` carries an **`allowed_sites`** registry; a decoded site not in it is quarantined as **`unknown_site`** rather than silently defaulted. Supersedes the silent-fallback behavior.

- **PM-021 — dedup by highest seq / `superseded`.** Re-uploads and overlapping field syncs meant the same `dev` appeared multiple times. Rule: keep the **highest `seq`**, quarantine older same-dev captures as **`superseded`**. Supersedes any "keep the first one seen" or "keep the newest file mtime" behavior.

- **ERRATA-019 — quarantine order is fixed and first-match-wins.** Because a capture can trip several rules, the evaluation order was pinned: `missing_calibration` → `bad_checksum` → `sensor_variant_c` → `unknown_site` → `superseded`, first match wins, exactly one reason. Supersedes any version that reported multiple reasons or evaluated them in a different order (early code listed `sensor_variant_c` before `bad_checksum`, which mislabeled truncated Variant-C blobs).

If you're keeping score: the body of this notebook is a fossil record. The change log above is what's actually true today.

### A.11 — Quick pre-flight checklist

Before you trust a manifest you generated, walk this:

- [ ] CRC implementation returns `0x29B1` for `"123456789"`.
- [ ] You base64-decoded the chunk value **before** parsing bytes.
- [ ] Multi-byte fields read **big-endian**.
- [ ] `wb` divided by 10000.
- [ ] `co` bytes 15–17 **skipped**, mapping taken from the **variant**.
- [ ] Variant B uses **RED←slot2, GREEN←slot1, NIR←slot0**.
- [ ] When both keys present, **2.x wins**.
- [ ] Scales rounded to **6dp**.
- [ ] `source_png` is **bare** filename; `sensor_variant` is a **single letter**.
- [ ] `input_size` and `confidence_threshold` ignore the device; `labels_version` is global for ordinary sites and site-supplied for pilot sites (site-alpha).
- [ ] Quarantine reasons evaluated in the fixed order, one reason each.
- [ ] Dedup keeps highest `seq`; losers are `superseded`.
- [ ] `devices` sorted by `device_id`; `quarantined` sorted by `source_png`.

### A.12 — Sign-off

That's the book. It started as a shared text file on a damp laptop and turned into the closest thing we have to a spec, which is to say it's honest about being wrong sometimes and tries to tell you *when* it was wrong. Keep appending. Date your entries. When you correct something, say what you're superseding and point at the byte, the field, or the run that proved it. The next engineer reading this on a boat at 2am — possibly you, in six months, having forgotten all of it — will thank you for the citation.

Trust the errata, not the cheat-sheet. Decode the base64. Skip the `co` bytes. Big-endian, /10000, CRC must hit `0x29B1`. Ship the manifest, quarantine honestly, and write down what surprised you.

— ReefBox field engineering, sign-off on the appendix. Latest entry wins; if you found something newer than this page, you know what to do.
