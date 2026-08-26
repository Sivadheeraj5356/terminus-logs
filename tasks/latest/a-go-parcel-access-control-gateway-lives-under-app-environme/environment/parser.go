package main

import ("strconv"; "strings")

func parseRequest(line string) (Request, bool) {
    fields := strings.Fields(line)
    if len(fields) != 8 || fields[0] != "REQ" { return Request{}, false }
    routeID, err := strconv.Atoi(fields[2]); if err != nil { return Request{}, false }
    units, err := strconv.Atoi(fields[6]); if err != nil { return Request{}, false }
    segment, err := strconv.Atoi(fields[7]); if err != nil { return Request{}, false }
    return Request{ID: fields[1], RouteID: routeID, Actor: fields[3], Scope: fields[4], Phase: fields[5], Units: units, Segment: segment}, true
}
