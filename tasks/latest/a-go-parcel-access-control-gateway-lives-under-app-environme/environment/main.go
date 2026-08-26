package main

import ("bufio"; "fmt"; "io"; "os"; "strings")

func main() {
    var input io.Reader = os.Stdin
    if len(os.Args) > 1 { file, err := os.Open(os.Args[1]); if err != nil { os.Exit(2) }; defer file.Close(); input = file }
    scanner := bufio.NewScanner(input)
    for scanner.Scan() {
        line := scanner.Text()
        if strings.TrimSpace(line) == "" || strings.HasPrefix(line, "#") { continue }
        req, ok := parseRequest(line); if !ok { continue }
        rule, ok := getRouteRule(req.RouteID)
        decision := "DENY"
        if ok && evaluate(rule, req) { decision = "ALLOW" }
        fmt.Printf("%s %s %d\n", req.ID, decision, req.RouteID)
    }
}
