# Rift Conclave rules, version 1

The input is one UTF-8 JSON object. Unknown fields, duplicate site IDs, duplicate card IDs, duplicate omen IDs, duplicate undirected edges, self-edges, references to unknown sites, values outside the ranges below, or any enum not listed here make the position invalid. All IDs are non-empty ASCII strings containing only letters, digits, `_`, or `-`.

The object has exactly these fields:

- `version`: integer `1`.
- `rounds`: integer 1–5.
- `energy`, `energy_cap`: integers 0–12, with `energy <= energy_cap`.
- `channel_tokens`, `rotate_tokens`, `focus_tokens`: integers 0–2.
- `strain_limit`: integer 1–6.
- `sites`: 2–4 objects. Each has exactly `id`, `attunement`, `power`, `ward`, `strain`, `curse`, `threshold`, and `value`. Attunement is `sun`, `moon`, or `star`; `power`, `ward`, and `strain` are integers 0–12, `curse` is an integer 0–4, and `threshold` and `value` are integers 1–12.
- `edges`: undirected pairs of distinct site IDs. Every site must be reachable from every other site. Either endpoint order is valid in the input: `["b","a"]` and `["a","b"]` describe the same edge and therefore cannot both occur. Canonicalize each accepted edge internally as its lexicographically smaller endpoint followed by its larger endpoint for keys, sorting, rotate output, and duplicate detection; do not reject a position merely because an input pair is reversed.
- `cards`: 1–6 objects, each with exactly `id`, `school`, `style`, `power`, and `cost`. School uses the attunement enum, style is `strike`, `aegis`, or `link`, power is an integer 1–8, and cost is an integer 0–8.
- `omens`: 0–5 objects, each with exactly `id`, `kind`, `magnitude`, and `targets`. Kind is `drain`, `fracture`, `eclipse`, `curse`, or `tax`; magnitude is an integer 1–4. A tax has an empty targets array. Every other omen has 1–4 distinct known site IDs. Target array order has no meaning.

Site, card, omen, target, and edge input order never breaks ties. Comparisons use bytewise ascending ID order.

## Round sequence

The player acts first in every round. A card and an omen can each be used only once in the whole game. The remembered school begins empty. A deploy replaces it with that card's school, and it persists through the rival action and across round boundaries until another deploy replaces it or a non-deploy player action clears it.

The legal player actions are:

- `deploy`: choose an unused card whose cost does not exceed current energy and choose any site. Pay the cost. Let `gain` be the card power, plus 2 when its school equals the site's attunement at that instant, plus 1 when the immediately preceding player action was a deploy of the same school. Add gain to the target's power. If the target was controlled immediately before this deploy, add 1 strain to it. Style `aegis` then adds 2 ward to the target. Style `link` then adds 1 power to every adjacent site. Style `strike` has no additional effect. The deployed card's school becomes the remembered school.
- `channel`: requires a channel token. Spend one channel token, add 2 energy without exceeding `energy_cap`, then add 1 ward and 1 strain to the chosen site. Clear the remembered school.
- `rotate`: requires a rotate token and at least 1 energy. Spend one token and 1 energy, choose an edge, and swap the two endpoint attunements. Clear the remembered school.
- `focus`: requires a focus token and at least 1 energy. Spend one token and 1 energy, then choose an edge and a direction along it. First move exactly `min(2, source ward)` ward from the source endpoint to the destination endpoint: move 2 when at least 2 are available, otherwise move all available ward. Then, if the source has any power, move exactly 1 power from the source to the destination. Finally add 1 strain to the destination. Clear the remembered school. The source and destination order matters, even when one or both transfers move nothing.
- `rest`: always legal. Add 1 energy without exceeding `energy_cap` and clear the remembered school.

A site is controlled whenever `power >= threshold` and `strain < strain_limit`. “Controlled immediately before deploy” is evaluated before paying for or applying that deploy; link gains never create extra deploy strain.

After the player action, the rival must use one remaining omen. If none remain, the rival passes. For `drain`, `fracture`, and `eclipse`, the rival also chooses one site from that omen's targets. Apply the chosen omen as follows:

- `drain`: ward absorbs as much magnitude as possible and is consumed by that amount; remaining magnitude removes power, stopping at zero.
- `fracture`: ward absorbs and is consumed in the same way; remaining magnitude adds strain.
- `eclipse`: if the target has any ward, consume exactly 1 ward and cancel the omen. Otherwise advance its attunement by magnitude steps around `sun -> moon -> star -> sun`.
- `curse`: add its magnitude to the target's curse. Curse has no runtime cap; the 0–4 bound applies only to each site's input value.
- `tax`: reduce energy by magnitude, stopping at zero. It has no target.

At round end, resolve each site in ascending site-ID order as follows. If its curse is positive, including curse just added by the rival in that round, it first loses exactly 1 power, stopping at zero, and then its curse decreases by exactly 1. Next, if its strain is at least `strain_limit`, it loses another 1 power, stopping at zero. Site order does not change the result. After all sites resolve, add 1 energy for each currently controlled site, without exceeding `energy_cap`. Nothing else recovers or decays. These effects occur after every round, including the last. Curse loss and overload loss are additive: a site subject to both can lose 2 power in the same round.

## Score and canonical play

After the requested rounds, score the position as:

1. the sum of `value` for controlled sites;
2. plus 2 for each distinct attunement among controlled sites;
3. plus 4 if every site is controlled;
4. plus remaining energy;
5. minus the sum of all site strain.

The player chooses actions to maximize the score they can guarantee against rival play. The rival chooses to minimize that guaranteed final score. At each individual player decision, equal-score actions are resolved by the lexicographically smallest local player key; future line text is not consulted. At each individual rival decision, equal-score actions are resolved by the lexicographically smallest local rival key; future line text is not consulted.

Player keys are exactly:

- `deploy|CARD_ID|SITE_ID`
- `channel|SITE_ID`
- `rotate|LOW_ENDPOINT|HIGH_ENDPOINT`
- `focus|SOURCE_ENDPOINT|DESTINATION_ENDPOINT`
- `rest`

Rival keys are `omen|OMEN_ID|SITE_ID`, `omen|OMEN_ID|-` for tax, or `pass`. A rival cannot pass while an omen remains.

The output is one JSON object with exactly `guaranteed_score`, `line`, and `final`. `line` contains one object per round in chronological order, each with exactly `round`, `player`, and `rival`. Player objects always contain exactly `kind`, `card`, `site`, and `edge`; unused fields are JSON null. Rotate uses the canonical low-ID/high-ID edge array. Focus uses the ordered source/destination edge array, which is not canonicalized. Rival objects always contain exactly `kind`, `omen`, and `site`. For every used omen, rival `kind` is the literal action category string `"omen"`, never the omen's input kind such as `"drain"` or `"fracture"`. Pass uses `kind: "pass"` with null omen and site; tax uses `kind: "omen"`, its omen ID, and null site.

`final` contains exactly `energy`, `controlled`, and `sites`. Controlled IDs are sorted ascending. Final sites are sorted by ID and each contains exactly `id`, `attunement`, `power`, `ward`, `strain`, `curse`, and `controlled`. The output must end with one newline. Empty arrays remain arrays, never null.
