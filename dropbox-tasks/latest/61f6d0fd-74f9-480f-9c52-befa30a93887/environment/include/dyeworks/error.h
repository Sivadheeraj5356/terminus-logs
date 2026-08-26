#ifndef DYEWORKS_ERROR_H
#define DYEWORKS_ERROR_H

/* Every parsing subsystem reports a rejected input through this one helper so
 * the failing path names itself on stderr. The recognised subsystem names are:
 * header, sectab, uleb, dyeworksdef, node, form, lot, str, format. */
int dyeworks_error(const char *subsystem, const char *fmt, ...);

#endif
