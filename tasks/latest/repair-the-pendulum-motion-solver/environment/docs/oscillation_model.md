# Damped oscillation model

Each capture is a damped planar pendulum whose horizontal bob displacement follows

    x(t) = A * exp(-gamma * t) * cos(2 * pi * f * t + phi)

where `f` is natural frequency in hertz and `gamma` is the decay rate in per second units.
The driver must recover `frequency_hz` and `decay_per_second` for every job from the decoded
frames rather than from stored metadata.
