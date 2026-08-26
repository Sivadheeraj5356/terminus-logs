require 'json'

module HealthRoutes
  def self.handle(req, res)
    res.status = 200
    res['Content-Type'] = 'application/json'
    res.body = JSON.generate({ status: 'ok', service: 'obsidian-vault' })
  end
end
