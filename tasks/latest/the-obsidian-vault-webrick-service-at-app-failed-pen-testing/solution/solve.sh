#!/bin/bash
# Oracle for flat ruby-webrick-escape-room-hardening: full hardening + Go prop tests.
set -euo pipefail

SETTINGS=/app/config/settings.yaml
ADMIN_ROUTES=/app/routes/admin_routes.rb
NONCE_STORE=/app/lib/nonce_store.rb

# --- Admin auth hardening ---
ruby -e "
require 'yaml'
cfg = YAML.safe_load(File.read('$SETTINGS'))
cfg['admin_secret'] = 'changeme-in-production'
File.write('$SETTINGS', cfg.to_yaml)
"

cat << 'RUBY' > "$NONCE_STORE"
require 'set'

class NonceStore
  def initialize
    @seen  = Set.new
    @mutex = Mutex.new
  end

  def record!(nonce)
    @mutex.synchronize do
      return false if @seen.include?(nonce)
      @seen.add(nonce)
      true
    end
  end
end
RUBY

cat << 'RUBY' > "$ADMIN_ROUTES"
require 'json'
require 'openssl'

module AdminRoutes
  def self.json_response(res, body, status: 200)
    res.status = status
    res['Content-Type'] = 'application/json'
    res.body = JSON.generate(body)
  end

  def self.forbidden_unless_signed(req, res)
    ts    = req['x-timestamp']
    sig   = req['x-admin-signature']
    nonce = req['x-nonce']

    unless ts && sig && nonce
      res.status = 403
      res.body = '{"error":"forbidden"}'
      return true
    end

    ts_i = ts.to_i
    now  = Time.now.to_i
    if (ts_i - now).abs > 90
      res.status = 403
      res.body = '{"error":"forbidden"}'
      return true
    end

    secret = $settings['admin_secret'] || ''
    expected_sig = OpenSSL::HMAC.hexdigest('SHA256', secret, "#{req.path}:#{ts}:#{nonce}")

    unless sig == expected_sig
      res.status = 403
      res.body = '{"error":"forbidden"}'
      return true
    end

    unless $nonce_store.record!(nonce)
      res.status = 403
      res.body = '{"error":"forbidden","reason":"replay"}'
      return true
    end

    false
  end

  def self.handle_debug_dump(req, res)
    return if forbidden_unless_signed(req, res)
    unless req.request_method == 'POST'
      return json_response(res, { error: 'method not allowed' }, status: 405)
    end
    json_response(res, {
      debug: true,
      settings: $settings.reject { |k, _| k == 'moderator_key' || k == 'admin_secret' },
      puzzle_state: $puzzle_engine.state,
      vault: $vault.status,
      sessions: $session_store.count
    })
  end

  def self.handle_force_unlock(req, res)
    return if forbidden_unless_signed(req, res)
    unless req.request_method == 'POST'
      return json_response(res, { error: 'method not allowed' }, status: 405)
    end
    $vault.force_open!
    json_response(res, { ok: true, message: 'vault force-opened', vault: $vault.status })
  end
end
RUBY

# --- Puzzle engine hardening ---
PUZZLE_ENGINE=/app/lib/puzzle_engine.rb

cat << 'RUBY' > "$PUZZLE_ENGINE"
require 'digest'

class PuzzleEngine
  MODERATOR_VERBS = %w[reset_puzzle set_attempts reveal_answer].freeze

  def initialize(room_def, settings)
    @settings  = settings
    @puzzles   = deep_copy(room_def['puzzles'])
    @vault_def = room_def['vault']
    @solved    = {}
    @mutex     = Mutex.new
  end

  def attempt(puzzle_id, answer)
    return { ok: false, reason: :unknown_puzzle } unless puzzle_exists?(puzzle_id)

    @mutex.synchronize do
      puzzle = find_puzzle(puzzle_id)
      return { ok: false, reason: :no_attempts } if puzzle['attempts_remaining'] <= 0
      return { ok: false, reason: :prereq_unmet } unless prereq_met?(puzzle_id)

      puzzle['attempts_remaining'] -= 1

      expected = puzzle['answer_hash']
      given    = Digest::SHA256.hexdigest(answer.to_s.strip.downcase)

      if given == expected
        @solved[puzzle_id] = true
        { ok: true, unlocks: puzzle['unlocks'] }
      else
        { ok: false, reason: :wrong_answer, attempts_remaining: puzzle['attempts_remaining'] }
      end
    end
  end

  def state
    {
      puzzles: @puzzles.map { |p|
        { id: p['id'], solved: @solved.key?(p['id']), attempts_remaining: p['attempts_remaining'] }
      },
      vault_open: vault_open?
    }
  end

  def vault_open?
    @solved.key?('vault_door')
  end

  def all_puzzles_solved?
    @puzzles.all? { |p| @solved.key?(p['id']) }
  end

  private

  def puzzle_exists?(id)
    @puzzles.any? { |p| p['id'] == id }
  end

  def find_puzzle(id)
    @puzzles.find { |p| p['id'] == id }
  end

  def prereq_met?(puzzle_id)
    puzzle = find_puzzle(puzzle_id)
    return true unless puzzle
    prev = @puzzles.find { |p| p['unlocks'] == puzzle_id }
    return true unless prev
    @solved.key?(prev['id'])
  end

  def deep_copy(obj)
    Marshal.load(Marshal.dump(obj))
  end
end
RUBY

# --- Moderator auth and rate limiting ---
DISPATCHER=/app/lib/dispatcher.rb
RATE_LIMITER=/app/lib/rate_limiter.rb

ruby -e "
require 'yaml'
cfg = YAML.safe_load(File.read('$SETTINGS'))
cfg['moderator_key'] = 'secret123'
cfg['rate_limit_rpm'] = 30
File.write('$SETTINGS', cfg.to_yaml)
"

cat << 'RUBY' > "$RATE_LIMITER"
require 'time'

class RateLimiter
  def initialize(rpm)
    @limit   = rpm.to_i
    @windows = {}
    @mutex   = Mutex.new
  end

  def allow?(ip)
    @mutex.synchronize do
      now    = Time.now.to_i
      bucket = now / 60

      @windows[ip] ||= { bucket: bucket, count: 0 }
      entry = @windows[ip]

      if entry[:bucket] != bucket
        entry[:bucket] = bucket
        entry[:count]  = 0
      end

      entry[:count] += 1
      entry[:count] <= @limit
    end
  end
end
RUBY

cat << 'RUBY' > "$DISPATCHER"
require 'json'
require 'openssl'

class Dispatcher
  MODERATOR_VERBS = %w[reset_puzzle set_attempts reveal_answer grant_hint_token].freeze
  GAME_VERBS      = %w[examine unlock attempt hint use inspect].freeze

  def initialize(settings)
    @settings = settings
  end

  def dispatch(verb, payload, req = nil, raw_body = '')
    return { error: 'unknown verb', status: 400 } unless valid_verb?(verb)

    if req && $rate_limiter
      ip = req.peeraddr[3] rescue '0.0.0.0'
      unless $rate_limiter.allow?(ip)
        return { error: 'rate limit exceeded', status: 429 }
      end
    end

    if moderator_verb?(verb)
      secret = @settings['moderator_key']
      if secret.nil? || secret.to_s.strip.empty?
        return { error: 'forbidden', status: 403 }
      end
      expected_sig = OpenSSL::HMAC.hexdigest('SHA256', secret.to_s, raw_body)
      unless req && req['x-moderator-signature'] == expected_sig
        return { error: 'forbidden', status: 403 }
      end
      handle_moderator(verb, payload)
    else
      handle_game(verb, payload)
    end
  end

  private

  def valid_verb?(verb)
    MODERATOR_VERBS.include?(verb) || GAME_VERBS.include?(verb)
  end

  def moderator_verb?(verb)
    MODERATOR_VERBS.include?(verb)
  end

  def handle_moderator(verb, payload)
    case verb
    when 'reset_puzzle'
      { action: 'reset_puzzle', target: payload['puzzle_id'] }
    when 'set_attempts'
      { action: 'set_attempts', target: payload['puzzle_id'], value: payload['attempts'] }
    when 'reveal_answer'
      { action: 'reveal_answer', target: payload['puzzle_id'] }
    when 'grant_hint_token'
      { action: 'grant_hint_token', target: payload['session_id'] }
    end
  end

  def handle_game(verb, payload)
    { action: verb, target: payload['target'], data: payload['data'] }
  end
end
RUBY

# --- Go property-test suite ---
HARNESS=/app/prop_test/server_harness.go
TESTS=/app/prop_test/prop_test.go

cat > "$HARNESS" << 'GOEOF'
package proptest

import (
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"strings"
	"time"
)

type ServerHandle struct {
	cmd  *exec.Cmd
	addr string
}

func StartServer() (*ServerHandle, error) {
	port, err := freePort()
	if err != nil {
		return nil, fmt.Errorf("no free port: %w", err)
	}
	addr := fmt.Sprintf("127.0.0.1:%d", port)

	rubyopt := os.Getenv("RUBYOPT")
	if !strings.Contains(rubyopt, "-rbundler/setup") {
		if rubyopt == "" {
			rubyopt = "-rbundler/setup"
		} else {
			rubyopt = rubyopt + " -rbundler/setup"
		}
	}
	env := os.Environ()
	filtered := make([]string, 0, len(env)+4)
	for _, e := range env {
		if !strings.HasPrefix(e, "RUBYOPT=") {
			filtered = append(filtered, e)
		}
	}
	filtered = append(filtered,
		fmt.Sprintf("PORT=%d", port),
		"BIND_ADDR=127.0.0.1",
		"RUBYOPT="+rubyopt,
		"RATE_LIMIT_RPM=10000",
	)

	cmd := exec.Command("ruby", "/app/server.rb")
	cmd.Dir = "/app"
	cmd.Env = filtered
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("start ruby: %w", err)
	}

	h := &ServerHandle{cmd: cmd, addr: addr}
	if err := waitHealthy(addr, 15*time.Second); err != nil {
		_ = cmd.Process.Kill()
		return nil, err
	}
	return h, nil
}

func StopServer(h *ServerHandle) {
	if h == nil || h.cmd == nil {
		return
	}
	_ = h.cmd.Process.Kill()
	_ = h.cmd.Wait()
}

func (h *ServerHandle) BaseURL() string {
	return "http://" + h.addr
}

func waitHealthy(addr string, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	client   := &http.Client{Timeout: 500 * time.Millisecond}
	url      := "http://" + addr + "/health"
	for time.Now().Before(deadline) {
		resp, err := client.Get(url)
		if err == nil && resp.StatusCode == 200 {
			resp.Body.Close()
			return nil
		}
		time.Sleep(150 * time.Millisecond)
	}
	return fmt.Errorf("server at %s did not become healthy within %s", addr, timeout)
}

func freePort() (int, error) {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, err
	}
	defer l.Close()
	return l.Addr().(*net.TCPAddr).Port, nil
}
GOEOF

cat > "$TESTS" << 'GOEOF'
package proptest

import (
	"bytes"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	mrand "math/rand"
	"net/http"
	"os"
	"regexp"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func readModeratorKey() string {
	b, err := os.ReadFile("/app/config/settings.yaml")
	if err != nil {
		return ""
	}
	re := regexp.MustCompile(`(?m)^moderator_key:\s*"?([^"\n]*)"?`)
	m := re.FindSubmatch(b)
	if m == nil {
		return ""
	}
	return string(m[1])
}

func readAdminSecret() string {
	b, err := os.ReadFile("/app/config/settings.yaml")
	if err != nil {
		return ""
	}
	re := regexp.MustCompile(`(?m)^admin_secret:\s*"?([^"\n]*)"?`)
	m := re.FindSubmatch(b)
	if m == nil {
		return ""
	}
	return string(m[1])
}

func hmacSHA256Hex(key, data string) string {
	mac := hmac.New(sha256.New, []byte(key))
	mac.Write([]byte(data))
	return hex.EncodeToString(mac.Sum(nil))
}

func newSession(baseURL string) (string, error) {
	resp, err := http.Post(baseURL+"/session/new", "application/json", bytes.NewReader([]byte("{}")))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	var m map[string]string
	json.NewDecoder(resp.Body).Decode(&m)
	return m["session_id"], nil
}

func newUUID() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	return fmt.Sprintf("%08x-%04x-%04x-%04x-%012x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:])
}

func randomPayload(rng *mrand.Rand) []byte {
	verbs := []string{"reset_puzzle", "force_unlock", "examine", "VAULT-7-OVERRIDE", ""}
	seeds := []string{"", "admin", "random"}
	randStr := func(n int) string {
		const letters = "abcdefghijklmnopqrstuvwxyz0123456789"
		b := make([]byte, n)
		for i := range b {
			b[i] = letters[rng.Intn(len(letters))]
		}
		return string(b)
	}
	payload := map[string]interface{}{
		"verb":    verbs[rng.Intn(len(verbs))],
		"seed":    seeds[rng.Intn(len(seeds))],
		"payload": map[string]interface{}{"target": randStr(6), "data": randStr(4)},
	}
	b, _ := json.Marshal(payload)
	return b
}

func TestDebugEndpointsReturn403UnderDefaultConfig(t *testing.T) {
	srv, err := StartServer()
	if err != nil {
		t.Fatalf("start server: %v", err)
	}
	defer StopServer(srv)

	endpoints := []string{"/admin/debug-dump", "/admin/force-unlock"}
	rng := mrand.New(mrand.NewSource(time.Now().UnixNano()))

	for i := 0; i < 50; i++ {
		body := randomPayload(rng)
		for _, ep := range endpoints {
			resp, err := postJSON(srv.BaseURL(), ep, body, nil)
			if err != nil {
				t.Errorf("iter %d %s: %v", i, ep, err)
				continue
			}
			resp.Body.Close()
			if resp.StatusCode == 200 {
				t.Errorf("iter %d %s: expected 403/404, got %d", i, ep, resp.StatusCode)
			}
		}
	}
}

func TestGameEndpointAcceptsValidCommand(t *testing.T) {
	srv, err := StartServer()
	if err != nil {
		t.Fatalf("start server: %v", err)
	}
	defer StopServer(srv)

	body := mustMarshal(map[string]interface{}{
		"verb":    "examine",
		"payload": map[string]interface{}{"target": "room", "data": nil},
	})
	resp, err := postJSON(srv.BaseURL(), "/command", body, nil)
	if err != nil {
		t.Fatalf("POST /command: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		t.Errorf("expected 2xx for valid game command, got %d", resp.StatusCode)
	}
}

func TestPuzzleAttemptIsThreadSafe(t *testing.T) {
	srv, err := StartServer()
	if err != nil {
		t.Fatalf("start server: %v", err)
	}
	defer StopServer(srv)

	sessionID, err := newSession(srv.BaseURL())
	if err != nil || sessionID == "" {
		t.Fatalf("failed to create session: %v", err)
	}

	body := mustMarshal(map[string]interface{}{
		"verb":    "attempt",
		"payload": map[string]interface{}{"target": "cipher_alpha", "data": "wrong"},
	})
	headers := map[string]string{"X-Session-Token": sessionID}

	var wg sync.WaitGroup
	var evals, noAttempts int32

	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			resp, err := postJSON(srv.BaseURL(), "/command", body, headers)
			if err != nil {
				t.Errorf("POST /command error: %v", err)
				return
			}
			defer resp.Body.Close()
			respBody, _ := io.ReadAll(resp.Body)
			var m map[string]interface{}
			json.Unmarshal(respBody, &m)
			if reason, ok := m["reason"].(string); ok && reason == "no_attempts" {
				atomic.AddInt32(&noAttempts, 1)
			} else {
				atomic.AddInt32(&evals, 1)
			}
		}()
	}
	wg.Wait()

	if evals != 3 {
		t.Errorf("expected exactly 3 evaluated attempts (cipher_alpha limit=3), got %d", evals)
	}
	if noAttempts < 95 {
		t.Errorf("expected at least 95 no_attempts rejections, got %d", noAttempts)
	}
	if evals+noAttempts > 100 {
		t.Errorf("expected evaluated + no_attempts <= 100, got %d (%d evaluated, %d no_attempts)", evals+noAttempts, evals, noAttempts)
	}
}

func TestModeratorEndpointsRequireHMAC(t *testing.T) {
	srv, err := StartServer()
	if err != nil {
		t.Fatalf("start server: %v", err)
	}
	defer StopServer(srv)

	secret := readModeratorKey()
	if secret == "" {
		t.Fatal("moderator_key is empty in settings.yaml")
	}

	body := mustMarshal(map[string]interface{}{
		"verb":    "reset_puzzle",
		"payload": map[string]interface{}{"puzzle_id": "cipher_alpha"},
	})

	sig := hmacSHA256Hex(secret, string(body))
	headers := map[string]string{"X-Moderator-Signature": sig}
	resp, err := postJSON(srv.BaseURL(), "/command", body, headers)
	if err != nil {
		t.Fatalf("POST /command good sig: %v", err)
	}
	resp.Body.Close()
	if resp.StatusCode == 403 {
		t.Errorf("correct HMAC signature rejected with 403")
	}

	badHeaders := map[string]string{"X-Moderator-Signature": "invalid"}
	badResp, err := postJSON(srv.BaseURL(), "/command", body, badHeaders)
	if err != nil {
		t.Fatalf("POST /command bad sig: %v", err)
	}
	badResp.Body.Close()
	if badResp.StatusCode != 403 {
		t.Errorf("expected 403 for bad signature, got %d", badResp.StatusCode)
	}
}

func TestAdminEndpointRejectsReplay(t *testing.T) {
	srv, err := StartServer()
	if err != nil {
		t.Fatalf("start server: %v", err)
	}
	defer StopServer(srv)

	secret := readAdminSecret()
	if secret == "" {
		t.Fatal("admin_secret is empty in settings.yaml")
	}

	nonce := newUUID()
	ts := fmt.Sprintf("%d", time.Now().Unix())
	path := "/admin/debug-dump"
	sig := hmacSHA256Hex(secret, path+":"+ts+":"+nonce)

	headers := map[string]string{
		"X-Timestamp":       ts,
		"X-Nonce":           nonce,
		"X-Admin-Signature": sig,
	}
	resp1, err := postJSON(srv.BaseURL(), path, []byte("{}"), headers)
	if err != nil {
		t.Fatalf("first request: %v", err)
	}
	resp1.Body.Close()
	if resp1.StatusCode != 200 {
		t.Fatalf("first request expected 200, got %d", resp1.StatusCode)
	}

	resp2, err := postJSON(srv.BaseURL(), path, []byte("{}"), headers)
	if err != nil {
		t.Fatalf("replay request: %v", err)
	}
	resp2.Body.Close()
	if resp2.StatusCode != 403 {
		t.Errorf("replay expected 403, got %d", resp2.StatusCode)
	}
}

func postJSON(baseURL, path string, body []byte, headers map[string]string) (*http.Response, error) {
	url := baseURL + path
	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	return http.DefaultClient.Do(req)
}

func mustMarshal(v any) []byte {
	b, err := json.Marshal(v)
	if err != nil {
		panic(err)
	}
	return b
}
GOEOF

cd /app/prop_test
go test -v -count=1 -timeout 120s ./...
