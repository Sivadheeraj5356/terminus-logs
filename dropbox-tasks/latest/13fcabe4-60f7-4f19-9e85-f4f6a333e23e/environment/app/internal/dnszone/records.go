package dnszone

import "github.com/miekg/dns"

func FindSOA(z *Zone) *dns.SOA {
	for _, r := range z.Records {
		if r.Type == dns.TypeSOA {
			return r.RR.(*dns.SOA)
		}
	}
	return nil
}

func HasDelegation(z *Zone, name string) bool {
	fqdn := dns.Fqdn(name)
	for _, r := range z.Records {
		if r.Type == dns.TypeNS && r.Owner == fqdn {
			return true
		}
	}
	return false
}
