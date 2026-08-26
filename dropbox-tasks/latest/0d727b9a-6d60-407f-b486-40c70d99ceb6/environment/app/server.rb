require 'webrick'
require 'json'
require 'yaml'
require_relative 'lib/session_store'
require_relative 'lib/puzzle_engine'
require_relative 'lib/dispatcher'
require_relative 'lib/vault'
require_relative 'lib/hint_engine'
require_relative 'lib/nonce_store'
require_relative 'lib/rate_limiter'
require_relative 'routes/game_routes'
require_relative 'routes/admin_routes'
require_relative 'routes/health_routes'

config_path = File.join(__dir__, 'config', 'settings.yaml')
$settings   = YAML.safe_load_file(config_path)

messages_path = File.join(__dir__, 'config', 'messages.yaml')
$messages     = YAML.safe_load_file(messages_path)

room_path = File.join(__dir__, 'config', 'room.yaml')
$room_def = YAML.safe_load_file(room_path)

$session_store  = SessionStore.new($settings['session_timeout'])
$puzzle_engine  = PuzzleEngine.new($room_def, $settings)
$dispatcher     = Dispatcher.new($settings)
$vault          = Vault.new($room_def['vault'])
$hint_engine    = HintEngine.new($room_def)
$nonce_store    = NonceStore.new
$rate_limiter   = RateLimiter.new(ENV['RATE_LIMIT_RPM'] || $settings['rate_limit_rpm'] || 30)

port = (ENV['PORT'] || $settings['port'] || 8080).to_i
bind_addr = ENV['BIND_ADDR'] || $settings['bind_addr'] || '0.0.0.0'

log_level = $settings['log_level'] == 'debug' ? WEBrick::Log::DEBUG : WEBrick::Log::INFO

server = WEBrick::HTTPServer.new(
  Port:        port,
  BindAddress: bind_addr,
  Logger:      WEBrick::Log.new($stderr, log_level),
  AccessLog:   []
)

server.mount_proc '/health' do |req, res|
  HealthRoutes.handle(req, res)
end

server.mount_proc '/state' do |req, res|
  GameRoutes.handle_state(req, res)
end

server.mount_proc '/hint' do |req, res|
  GameRoutes.handle_hint(req, res)
end

server.mount_proc '/session/new' do |req, res|
  GameRoutes.handle_new_session(req, res)
end

server.mount_proc '/command' do |req, res|
  GameRoutes.handle_command(req, res)
end

server.mount_proc '/admin/debug-dump' do |req, res|
  AdminRoutes.handle_debug_dump(req, res)
end

server.mount_proc '/admin/force-unlock' do |req, res|
  AdminRoutes.handle_force_unlock(req, res)
end

trap('INT')  { server.shutdown }
trap('TERM') { server.shutdown }

server.start
