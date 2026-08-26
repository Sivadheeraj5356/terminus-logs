package main

import (
	"bytes"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"os"
	"sort"
	"strings"
)

type DS struct { KeyTag uint16 `json:"key_tag"`; Algorithm uint8 `json:"algorithm"`; DigestType uint8 `json:"digest_type"`; Digest string `json:"digest"` }
type Key struct { Flags uint16 `json:"flags"`; Protocol uint8 `json:"protocol"`; Algorithm uint8 `json:"algorithm"`; PublicKey string `json:"public_key"` }
type Sig struct { TypeCovered uint16 `json:"type_covered"`; Algorithm uint8 `json:"algorithm"`; Labels uint8 `json:"labels"`; OriginalTTL uint32 `json:"original_ttl"`; Expiration uint64 `json:"expiration"`; Inception uint64 `json:"inception"`; KeyTag uint16 `json:"key_tag"`; Signer string `json:"signer"`; Signature string `json:"signature"` }
type Set struct { Owner string `json:"owner"`; Type uint16 `json:"type"`; TTL uint32 `json:"ttl"`; Records []string `json:"records"`; Signatures []Sig `json:"signatures"` }
type Bundle struct { Now uint64 `json:"now"`; Zone string `json:"zone"`; ParentDS []DS `json:"parent_ds"`; DNSKeys []Key `json:"dnskeys"`; RRSets []Set `json:"rrsets"` }

func wire(s string) []byte { if s=="."{return []byte{0}}; var out []byte;for _,p:=range strings.Split(strings.TrimSuffix(strings.ToLower(s),"."),"."){out=append(out,byte(len(p)));out=append(out,[]byte(p)...)};return append(out,0) }
func tag(r []byte)uint16{var a uint32;for i,b:=range r{if i%2==0{a+=uint32(b)<<8}else{a+=uint32(b)}};a+=(a>>16)&65535;return uint16(a)}
func pubBytes(p *rsa.PublicKey)[]byte{e:=bigEndian(p.E);n:=p.N.Bytes();return append(append([]byte{byte(len(e))},e...),n...)}
func bigEndian(v int)[]byte{var x [8]byte;binary.BigEndian.PutUint64(x[:],uint64(v));i:=0;for i<7&&x[i]==0{i++};return x[i:]}
func signing(set Set,s Sig)[]byte{var b bytes.Buffer;binary.Write(&b,binary.BigEndian,s.TypeCovered);b.WriteByte(s.Algorithm);b.WriteByte(s.Labels);binary.Write(&b,binary.BigEndian,s.OriginalTTL);binary.Write(&b,binary.BigEndian,uint32(s.Expiration));binary.Write(&b,binary.BigEndian,uint32(s.Inception));binary.Write(&b,binary.BigEndian,s.KeyTag);b.Write(wire(s.Signer));owner:=wire(set.Owner);parts:=strings.Split(strings.TrimSuffix(set.Owner,"."),".");if int(s.Labels)==len(parts)-1{owner=wire("*."+strings.Join(parts[1:],".")+".")};var rrs [][]byte;for _,v:=range set.Records{r,_:=base64.StdEncoding.DecodeString(v);var q bytes.Buffer;q.Write(owner);binary.Write(&q,binary.BigEndian,set.Type);binary.Write(&q,binary.BigEndian,uint16(1));binary.Write(&q,binary.BigEndian,s.OriginalTTL);binary.Write(&q,binary.BigEndian,uint16(len(r)));q.Write(r);rrs=append(rrs,q.Bytes())};sort.Slice(rrs,func(i,j int)bool{return bytes.Compare(rrs[i],rrs[j])<0});for _,r:=range rrs{b.Write(r)};return b.Bytes()}
func makeBundle(priv *rsa.PrivateKey,zone,owner string,wild bool,records [][]byte)Bundle{pub:=pubBytes(&priv.PublicKey);rdata:=append([]byte{1,1,3,8},pub...);kt:=tag(rdata);d:=sha256.Sum256(append(wire(zone),rdata...));enc:=[]string{};for _,r:=range records{enc=append(enc,base64.StdEncoding.EncodeToString(r))};labels:=uint8(len(strings.Split(strings.TrimSuffix(owner,"."),".")));if wild{labels--};set:=Set{Owner:owner,Type:16,TTL:3600,Records:enc};s:=Sig{TypeCovered:16,Algorithm:8,Labels:labels,OriginalTTL:3600,Expiration:2000000000,Inception:1000000000,KeyTag:kt,Signer:zone};h:=sha256.Sum256(signing(set,s));raw,_:=rsa.SignPKCS1v15(rand.Reader,priv,crypto.SHA256,h[:]);s.Signature=base64.StdEncoding.EncodeToString(raw);set.Signatures=[]Sig{s};return Bundle{Now:1700000000,Zone:zone,ParentDS:[]DS{{kt,8,2,hex.EncodeToString(d[:])}},DNSKeys:[]Key{{257,3,8,base64.StdEncoding.EncodeToString(pub)}},RRSets:[]Set{set}}}
func main(){priv,_:=rsa.GenerateKey(rand.Reader,1024);cases:=map[string]Bundle{"valid":makeBundle(priv,"example.test.","www.example.test.",false,[][]byte{[]byte("b"),[]byte("a"),[]byte("a")}),"casefold":makeBundle(priv,"EXAMPLE.TEST.","WWW.Example.Test.",false,[][]byte{[]byte("z"),[]byte("m")}),"wildcard":makeBundle(priv,"example.test.","x.deep.example.test.",true,[][]byte{[]byte("wild")})};raw,_:=json.Marshal(cases);os.WriteFile(os.Args[1],raw,0644)}
