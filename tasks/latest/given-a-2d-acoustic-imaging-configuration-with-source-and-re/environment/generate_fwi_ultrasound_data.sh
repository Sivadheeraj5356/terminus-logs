#!/bin/bash
set -e

mkdir -p /app/config /app/data/fwi /app/output /var/lib/fwi-truth

python3 << 'PYGEN'
import json
import math
import random

random.seed(14142135)

NX = 20
NZ = 20
NUM_SOURCES = 8
NUM_RECEIVERS = 16
NUM_TIMESTEPS = 100
NUM_FREQUENCIES = 4
NUM_ITERATIONS = 5

settings = {
    "simulation_id": "FWI-ULTRASOUND-2026",
    "grid_nx": NX,
    "grid_nz": NZ,
    "dx_mm": 0.5,
    "dz_mm": 0.5,
    "dt_us": 0.01,
    "num_timesteps": NUM_TIMESTEPS,
    "num_sources": NUM_SOURCES,
    "num_receivers": NUM_RECEIVERS,
    "source_frequency_mhz": [1.0, 2.0, 3.0, 5.0],
    "num_inversion_iterations": NUM_ITERATIONS,
    "lbfgs_memory": 3,
    "initial_velocity_mps": 1500.0,
    "water_velocity_mps": 1480.0,
    "tissue_velocity_range_mps": [1400.0, 1600.0],
    "attenuation_alpha0_np_per_mhz_cm": 0.5,
    "attenuation_power_n": 1.1,
    "pml_thickness": 3,
    "pml_max_damping": 100.0,
    "misfit_norm": "L2",
    "step_length_initial": 0.01,
    "step_length_reduction": 0.5,
    "convergence_tolerance": 1e-6,
    "uncertainty_diagonal_hessian": True,
    "density_kg_per_m3": 1000.0,
    # Red herrings
    "transducer_element_pitch_mm": 0.3,
    "transducer_elevation_focus_mm": 20.0,
    "electrical_impedance_ohm": 50.0,
    "coupling_gel_thickness_mm": 1.0,
    "gpu_block_size_x": 16,
    "gpu_block_size_z": 16,
    "motion_compensation_enabled": False,
    "respiratory_rate_bpm": 15,
    "shear_wave_coupling": False,
}

random.seed(14142135 + 1)
true_velocity = []
for iz in range(NZ):
    row = []
    for ix in range(NX):
        r = math.sqrt((ix - NX/2)**2 + (iz - NZ/2)**2)
        if r < NX * 0.3:
            v = 1540.0 + random.uniform(-20, 20)
        elif r < NX * 0.15:
            v = 1580.0 + random.uniform(-10, 10)
        else:
            v = 1480.0
        row.append(round(v, 2))
    true_velocity.append(row)

true_attenuation = []
for iz in range(NZ):
    row = []
    for ix in range(NX):
        r = math.sqrt((ix - NX/2)**2 + (iz - NZ/2)**2)
        if r < NX * 0.3:
            a = 0.5 + random.uniform(-0.1, 0.1)
        else:
            a = 0.002
        row.append(round(a, 4))
    true_attenuation.append(row)

random.seed(14142135 + 2)
sources = []
for i in range(NUM_SOURCES):
    angle = 2 * math.pi * i / NUM_SOURCES
    radius = NX * 0.45
    sx = int(NX / 2 + radius * math.cos(angle))
    sz = int(NZ / 2 + radius * math.sin(angle))
    sx = max(0, min(NX - 1, sx))
    sz = max(0, min(NZ - 1, sz))
    sources.append({
        "source_id": f"SRC-{i+1:02d}",
        "position_ix": sx,
        "position_iz": sz,
        "waveform_type": "ricker",
        "peak_frequency_mhz": settings["source_frequency_mhz"][i % len(settings["source_frequency_mhz"])],
        "amplitude": 1.0,
        "delay_us": round(random.uniform(0, 0.05), 4),
    })

receivers = []
for i in range(NUM_RECEIVERS):
    angle = 2 * math.pi * i / NUM_RECEIVERS
    radius = NX * 0.45
    rx = int(NX / 2 + radius * math.cos(angle))
    rz = int(NZ / 2 + radius * math.sin(angle))
    rx = max(0, min(NX - 1, rx))
    rz = max(0, min(NZ - 1, rz))
    receivers.append({
        "receiver_id": f"RCV-{i+1:02d}",
        "position_ix": rx,
        "position_iz": rz,
    })

random.seed(14142135 + 3)
observed_data = []
for src_idx in range(NUM_SOURCES):
    src_data = []
    for rcv_idx in range(NUM_RECEIVERS):
        src_pos = (sources[src_idx]["position_ix"], sources[src_idx]["position_iz"])
        rcv_pos = (receivers[rcv_idx]["position_ix"], receivers[rcv_idx]["position_iz"])
        dist = math.sqrt((src_pos[0] - rcv_pos[0])**2 + (src_pos[1] - rcv_pos[1])**2) * settings["dx_mm"]
        avg_vel = 1500.0
        travel_time = dist / avg_vel * 1000
        freq = sources[src_idx]["peak_frequency_mhz"]

        waveform = []
        for t in range(NUM_TIMESTEPS):
            time_us = t * settings["dt_us"]
            tau = time_us - travel_time - sources[src_idx]["delay_us"]
            arg = (math.pi * freq * tau) ** 2
            ricker = (1.0 - 2.0 * arg) * math.exp(-arg)
            atten = math.exp(-settings["attenuation_alpha0_np_per_mhz_cm"] * freq**settings["attenuation_power_n"] * dist / 10.0)
            signal = ricker * atten + random.gauss(0, 0.01)
            waveform.append(round(signal, 8))
        src_data.append(waveform)
    observed_data.append(src_data)

with open("/app/config/settings.json", "w") as f:
    json.dump(settings, f, indent=2)

with open("/var/lib/fwi-truth/true_velocity.json", "w") as f:
    json.dump({"velocity_mps": true_velocity, "nx": NX, "nz": NZ}, f, indent=2)

with open("/var/lib/fwi-truth/true_attenuation.json", "w") as f:
    json.dump({"attenuation": true_attenuation, "nx": NX, "nz": NZ}, f, indent=2)

with open("/app/data/fwi/sources.json", "w") as f:
    json.dump({"sources": sources}, f, indent=2)

with open("/app/data/fwi/receivers.json", "w") as f:
    json.dump({"receivers": receivers}, f, indent=2)

with open("/app/data/fwi/observed_data.json", "w") as f:
    json.dump({"data": observed_data, "num_sources": NUM_SOURCES,
               "num_receivers": NUM_RECEIVERS, "num_timesteps": NUM_TIMESTEPS}, f, indent=2)

print(f"Generated {NX}x{NZ} grid, {NUM_SOURCES} sources, {NUM_RECEIVERS} receivers, "
      f"{NUM_TIMESTEPS} timesteps, {NUM_FREQUENCIES} frequencies")
PYGEN

echo "Environment setup complete."
