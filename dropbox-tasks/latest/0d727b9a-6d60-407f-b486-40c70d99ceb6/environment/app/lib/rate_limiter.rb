require 'time'

class RateLimiter
  def initialize(rpm)
    @limit   = rpm.to_i
    @windows = {}
  end

  def allow?(ip)
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
