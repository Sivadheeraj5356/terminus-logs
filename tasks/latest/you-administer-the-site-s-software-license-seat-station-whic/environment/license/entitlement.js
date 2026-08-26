"use strict";

function eligibleSeats(request, seats, rules, config) {
  const table = (rules && rules.entitlement) || {};
  const sources = table[request.edition] || [];
  return seats.filter((s) => sources.includes(s.edition));
}

module.exports = { eligibleSeats };
