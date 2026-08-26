package netroute

import "net/url"

func ProxyURL(endpoint string) *url.URL {
	u, err := url.Parse(endpoint)
	if err != nil {
		return nil
	}
	return u
}
