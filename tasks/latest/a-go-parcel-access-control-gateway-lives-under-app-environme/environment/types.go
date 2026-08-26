package main

type Request struct { ID string; RouteID int; Actor string; Scope string; Phase string; Units int; Segment int }
type Rule struct { Actor string; Scope string; Phase string; Limit int; Mode string }
