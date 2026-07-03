"""Non-battery telemetry simulator.

Generates a realistic daily-aggregated history for a vehicle (motor/controller
thermals, usage, harsh-driving and safety events). Each vehicle has a ground-truth
PROFILE that injects a recognisable signature, so the defect-vs-abuse AI has
something true to detect:

  normal        - healthy bands, gentle wear
  abuse         - hot motor/controller, frequent harsh driving, overcurrent
  latent_defect - one component's temperature trends abnormal over time WITHOUT
                  abuse -> looks like a manufacturing defect
  water_impact  - a discrete water-ingress / impact safety event in the history

Statistical (numpy) — there is no public per-VIN motor telemetry to anchor on.
Deterministic per VIN (seeded) so a vehicle's history is stable across calls.
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta

import numpy as np

PROFILES = ("normal", "abuse", "latent_defect", "water_impact")

MOTOR_OVERTEMP = 90.0
CTRL_OVERTEMP = 85.0


def _seed(vin: str) -> int:
    return int(hashlib.sha256(vin.encode()).hexdigest(), 16) % (2**32)


def generate(vin: str, profile: str = "normal", days: int = 180,
             end: date | None = None) -> list[dict]:
    rng = np.random.default_rng(_seed(vin) + PROFILES.index(profile if profile in PROFILES else "normal"))
    end = end or date.today()
    start = end - timedelta(days=days - 1)

    t = np.arange(days)
    # Seasonal ambient (sinusoid over the year) + noise.
    ambient = 18 + 9 * np.sin(2 * np.pi * (t / 365.0)) + rng.normal(0, 2.5, days)

    # Daily usage.
    distance = np.clip(rng.normal(42, 18, days), 0, None)

    # Baseline thermals scale with ambient + load (distance).
    load = distance / 50.0
    motor_avg = 45 + 0.6 * ambient + 12 * load + rng.normal(0, 3, days)
    ctrl_avg = 40 + 0.5 * ambient + 9 * load + rng.normal(0, 3, days)

    harsh_accel = rng.poisson(0.6, days)
    harsh_brake = rng.poisson(0.7, days)
    overcurrent = rng.poisson(0.05, days)
    water = np.zeros(days, dtype=int)
    impact = np.zeros(days, dtype=int)
    faults: list[list] = [[] for _ in range(days)]

    if profile == "abuse":
        motor_avg += rng.uniform(14, 22)
        ctrl_avg += rng.uniform(10, 16)
        harsh_accel = rng.poisson(4.5, days)
        harsh_brake = rng.poisson(4.0, days)
        overcurrent = rng.poisson(0.8, days)
        distance = np.clip(distance * 1.4, 0, None)
    elif profile == "latent_defect":
        # One component drifts upward over time with no abuse signature.
        comp = rng.integers(0, 2)
        ramp = np.linspace(0, rng.uniform(18, 30), days)
        if comp == 0:
            motor_avg += ramp
        else:
            ctrl_avg += ramp
        # A related fault appears late in life.
        fday = int(days * 0.8)
        faults[fday].append({"code": "P0A3F", "desc": "Motor electronics over-temperature",
                             "severity": "high"})
    elif profile == "water_impact":
        wday = int(rng.integers(int(days * 0.3), int(days * 0.9)))
        water[wday] = 1
        impact[wday] = 1
        faults[wday].append({"code": "B1676", "desc": "Water ingress detected",
                            "severity": "high"})

    motor_max = motor_avg + rng.uniform(12, 26, days)
    ctrl_max = ctrl_avg + rng.uniform(10, 20, days)
    odo = float(rng.uniform(2000, 8000))

    out: list[dict] = []
    for i in range(days):
        odo += float(distance[i])
        out.append({
            "vin": vin,
            "day": start + timedelta(days=i),
            "distance_km": round(float(distance[i]), 1),
            "odometer_km": round(odo, 1),
            "ambient_temp_c": round(float(ambient[i]), 1),
            "motor_temp_avg_c": round(float(motor_avg[i]), 1),
            "motor_temp_max_c": round(float(motor_max[i]), 1),
            "controller_temp_avg_c": round(float(ctrl_avg[i]), 1),
            "controller_temp_max_c": round(float(ctrl_max[i]), 1),
            "overcurrent_events": int(overcurrent[i]),
            "harsh_accel_count": int(harsh_accel[i]),
            "harsh_brake_count": int(harsh_brake[i]),
            "water_ingress_trip": int(water[i]),
            "impact_event": int(impact[i]),
            "fault_codes": faults[i] or None,
        })
    return out
