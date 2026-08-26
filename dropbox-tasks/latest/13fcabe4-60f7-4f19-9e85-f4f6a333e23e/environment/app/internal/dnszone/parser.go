package dnszone

import (
	"bufio"
	"fmt"
	"os"
	"sort"
	"strings"

	"github.com/miekg/dns"
)

type Record struct {
	Owner  string
	Type   uint16
	TTL    uint32
	RDATA  string
	Raw    string
	RR     dns.RR
}

type Zone struct {
	Origin  string
	Records []Record
}

func ParseFile(origin, path string) (*Zone, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return Parse(origin, string(data))
}

func Parse(origin, text string) (*Zone, error) {
	zone := &Zone{Origin: dns.Fqdn(origin)}
	scanner := bufio.NewScanner(strings.NewReader(text))
	var currentOrigin = zone.Origin
	var defaultTTL uint32 = 3600
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, ";") {
			continue
		}
		if strings.HasPrefix(line, "$ORIGIN") {
			parts := strings.Fields(line)
			if len(parts) >= 2 {
				currentOrigin = dns.Fqdn(parts[1])
			}
			continue
		}
		if strings.HasPrefix(line, "$TTL") {
			parts := strings.Fields(line)
			if len(parts) >= 2 {
				var ttl uint32
				fmt.Sscanf(parts[1], "%d", &ttl)
				defaultTTL = ttl
			}
			continue
		}
		owner, rest, ok := splitOwner(line, currentOrigin)
		if !ok {
			continue
		}
		fields := strings.Fields(rest)
		if len(fields) < 3 {
			continue
		}
		idx := 0
		var ttl uint32 = defaultTTL
		if _, err := fmt.Sscanf(fields[0], "%d", &ttl); err == nil {
			idx++
		}
		class := "IN"
		if idx < len(fields) && (fields[idx] == "IN" || fields[idx] == "CH") {
			class = fields[idx]
			idx++
		}
		_ = class
		if idx >= len(fields) {
			continue
		}
		rrtype := fields[idx]
		idx++
		rdata := strings.Join(fields[idx:], " ")
		rr, err := dns.NewRR(fmt.Sprintf("%s %d IN %s %s", owner, ttl, rrtype, rdata))
		if err != nil {
			return nil, fmt.Errorf("parse %q: %w", line, err)
		}
		zone.Records = append(zone.Records, Record{
			Owner: owner,
			Type:  rr.Header().Rrtype,
			TTL:   ttl,
			RDATA: rdata,
			Raw:   line,
			RR:    rr,
		})
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	sort.Slice(zone.Records, func(i, j int) bool {
		return CanonicalKey(zone.Records[i]) < CanonicalKey(zone.Records[j])
	})
	return zone, nil
}

func splitOwner(line, defaultOrigin string) (string, string, bool) {
	if strings.HasPrefix(line, "@") {
		parts := strings.SplitN(line, " ", 2)
		if len(parts) < 2 {
			return "", "", false
		}
		return defaultOrigin, parts[1], true
	}
	parts := strings.Fields(line)
	if len(parts) < 4 {
		return "", "", false
	}
	owner := parts[0]
	if !strings.HasSuffix(owner, ".") {
		if owner == "@" {
			owner = defaultOrigin
		} else {
			owner = dns.Fqdn(owner + strings.TrimSuffix(defaultOrigin, "."))
		}
	} else {
		owner = dns.Fqdn(owner)
	}
	return owner, strings.Join(parts[1:], " "), true
}

func SOASerial(z *Zone) (uint32, error) {
	for _, r := range z.Records {
		if r.Type == dns.TypeSOA {
			soa := r.RR.(*dns.SOA)
			return soa.Serial, nil
		}
	}
	return 0, fmt.Errorf("no SOA in zone")
}

func RenderUnsigned(z *Zone) string {
	var b strings.Builder
	b.WriteString(fmt.Sprintf("$ORIGIN %s\n$TTL 3600\n", z.Origin))
	for _, r := range z.Records {
		b.WriteString(fmt.Sprintf("%s %d IN %s %s\n", trimOwner(r.Owner, z.Origin), r.TTL, dns.TypeToString[r.Type], r.RDATA))
	}
	return b.String()
}

func TrimRelativeOwner(owner, origin string) string {
	return trimOwner(owner, origin)
}

func trimOwner(owner, origin string) string {
	if owner == origin {
		return "@"
	}
	suffix := strings.TrimSuffix(origin, ".")
	if strings.HasSuffix(strings.TrimSuffix(owner, "."), suffix) {
		rel := strings.TrimSuffix(strings.TrimSuffix(owner, "."), suffix)
		return strings.TrimSuffix(rel, ".")
	}
	return owner
}
