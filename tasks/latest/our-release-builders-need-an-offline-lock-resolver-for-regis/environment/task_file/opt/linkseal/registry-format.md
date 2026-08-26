# Linkseal registry format

Inputs are UTF-8 text. Trim leading and trailing ASCII whitespace. Ignore blank lines and lines whose first non-space byte is #. Fields are not escaped. Compatible inputs contain each policy key exactly once.

policy.cfg uses key=value lines: target is a token; flags is - or comma-separated tokens; toolchain_max, source_budget, image_budget, and risk_budget are unsigned decimal integers.

Each active roots.req line is one requirement. A requirement atom is cap@abi#lo..hi. abi, lo, and hi may each be *; other ABI values are unsigned integers and version bounds are major.minor.patch. Bounds are inclusive.

Read bytewise-sorted registry/*.pkg files whose basename starts seg_ followed by one or more decimal digits; those digits are the numeric segment id. Each active line has:

    name|version|targets|provides|requires|conflicts|toolchain|source|image|risk|cached

Names, targets, capabilities, and flags use lowercase ASCII letters, digits, ., _, or -. A version has three unsigned components. targets is * or a comma list. provides is a non-empty comma list of cap@abi with numeric ABI. requires is - or a comma list of atoms, optionally prefixed flag? or !flag?. A positive condition is active only when the flag is enabled; a negative condition is active only when absent. Inactive requirements create no obligation, but all other requirements of that release still apply.

conflicts is - or a comma list. An item without @ matches another selected package name. cap@abi matches a capability provided by another selected release; ABI * matches any ABI. Conflict declarations are one-way but any match rejects the whole final plan. Never compare a release with itself.

The last five fields are four unsigned integers and lowercase yes or no. Malformed release lines are ignored before duplicate handling. For equal name and version, retain the valid row with greatest segment id, then greatest 1-based physical line number, then bytewise-smallest filename. An otherwise valid row is usable only when its targets include the policy target or *, and toolchain <= toolchain_max.

A plan selects at most one version of each package. Every root and every active requirement of every selected release must have a selected provider with matching capability, ABI, and provider version range. Final-only ABI cohesion requires every selected provider of the same capability to expose the same ABI, including capabilities not used as witnesses. Other validation still applies when a requirement is already satisfied.

Source accounting is per selected release: cached=yes contributes zero, otherwise its source value. Image and risk always contribute their values. All three totals must be within policy budgets.

Rank complete feasible plans, in order, by: fewer selected releases; greater freshness; lower source; lower image; lower risk; bytewise-smaller signature. Freshness is the sum of major*1000000 + minor*1000 + patch. The signature is the comma-joined bytewise-sorted name@version list. No ranking level is local or per requirement.

Output is:

    TOTAL|count|freshness|source|image|risk

then, in bytewise package-name order:

    LOCK|name|version|segment|line|cached

Use the retained row's segment and physical line. If no plan exists, output UNSAT.

