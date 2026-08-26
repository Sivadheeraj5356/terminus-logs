# SPICE card contract

gaa_model.sp is plain text with Unix newlines and a single trailing newline after the last .param line. Header and parameter token spacing is normative: each header line begins with asterisk, then exactly one space, then the rest of the line. Parameter lines use `.param` followed by one space, then GROUP_NAME=VALUE with no spaces around the equals sign.

The card body is emitted as consecutive lines joined by single Unix newline characters: the three header comment lines, then for each fitted split_group one split_group comment line immediately followed by its nine .param lines, and finally exactly one trailing newline. Do not emit blank lines, indentation, carriage returns, or trailing spaces anywhere in the file, and do not insert separators between the header and the first group or between successive groups.

The first three lines are SPICE comment lines that each begin with an asterisk and a single space, then the rest of the line, in this exact order:

1. asterisk space schema space gaa-spice-v1, which renders as the characters * schema gaa-spice-v1
2. asterisk space reference_temp_c space then the reference temperature with one decimal place, which for the bundled corpus is the substring reference_temp_c 25.0 after the asterisk and space
3. asterisk space gaa compact model card, which renders as * gaa compact model card

The schema token is the literal word schema. The header uses schema rather than schema_version. The second and third header lines also require the asterisk comment prefix.

Emit one block per fitted split_group in ascending lexicographic order of the split_group name (for example A before B). Each block starts with a comment line asterisk space split_group space then the group name, followed by nine .param lines in this fixed order: vth0, u0, ss_factor, cgso, rsd, k1, ute, kt1, subth_weight.

Every .param line uses the form .param GROUP_NAME=VALUE with no spaces around the equals sign. Parameter names follow split_group underscore name such as A_vth0.

Scientific values for cgso and subth_weight must match Python 3 format string colon point 12 e exactly, including exponent sign and leading zeros after e such as 1.000000000000e-10, 6.000000000000e-06, and 1.500000000000e+00. The mantissa always carries exactly twelve digits after the decimal point and the exponent always carries an explicit sign and at least two digits, so a formatter that prints the exponent without the leading zero (for example 1.325e-6 instead of 1.325000000000e-06) does not satisfy this contract. All other parameters must match Python 3 format string colon point 6 f (six decimal fixed point), for example 0.400000; negative parameters keep the leading minus sign and six fractional digits such as -1.500000 and -0.020000. Emit all nine parameters in the fixed order including subth_weight.

model-fit writes the card from fitted groups and the tapeout reference temperature without reading bundled measurement files.

