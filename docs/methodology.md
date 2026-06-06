# Methodology

This document explains the engineering assumptions behind AI Race Engineer's
corner-level telemetry analysis. The goal is to make the model transparent:
what it measures, how the values should be interpreted, and where the current
heuristics are intentionally limited.

## Scope

The current analysis compares two drivers on the same session and estimates
where one driver gains or loses performance at corner level. It is designed as
a race-engineering support tool, not as an official timing system.

The analysis currently focuses on:

- corner segmentation from speed minima
- entry, apex, and exit speed comparison
- signed per-corner time-loss estimation
- driving-style indicators derived from speed, brake, and throttle behavior

## Data Source

Telemetry is loaded through FastF1. The relevant raw channels are transformed
into a corner-level feature table before comparison.

The feature pipeline extracts:

- `EntrySpeed`: speed at the start of the detected corner segment
- `ApexSpeed`: minimum speed inside the corner segment
- `ExitSpeed`: speed at the end of the detected corner segment
- `SpeedLoss`: `EntrySpeed - ApexSpeed`
- `SpeedGain`: `ExitSpeed - ApexSpeed`
- brake and throttle summary metrics when available

Speeds are handled in FastF1's standard telemetry unit, kilometres per hour
(km/h). Distances are handled in metres where used by the telemetry pipeline.
The final `TimeLoss` value is represented in seconds as an estimate, not as a
direct stopwatch measurement.

## Time-Loss Heuristic

The current time-loss model is a weighted linear estimate:

```text
TimeLoss =
    Delta_EntrySpeed * TIME_WEIGHT_ENTRY
  + Delta_ApexSpeed  * TIME_WEIGHT_APEX
  + Delta_ExitSpeed  * TIME_WEIGHT_EXIT
```

Current weights:

```text
TIME_WEIGHT_ENTRY = 0.015
TIME_WEIGHT_APEX  = 0.030
TIME_WEIGHT_EXIT  = 0.060
```

Where each delta is calculated as:

```text
Delta = driver_a_speed - driver_b_speed
```

A positive `TimeLoss` means driver A is estimated to gain time over driver B in
that corner. A negative `TimeLoss` means driver A is estimated to lose time to
driver B.

## Why Exit Speed Has The Highest Weight

Exit speed is weighted more strongly because it often affects the longest
downstream phase after a corner: acceleration onto the following straight or
the next section of track. A small speed advantage at corner exit can continue
to compound over many metres, whereas an entry-speed advantage may disappear
quickly if it compromises rotation, minimum speed, or traction.

The weighting order is therefore intentional:

```text
exit > apex > entry
```

This mirrors a common race-engineering interpretation:

- entry speed indicates braking confidence and turn-in approach
- apex speed indicates minimum-speed efficiency and corner rotation
- exit speed indicates traction, throttle application, and downstream speed

The weights are not universal physical constants. They are hand-tuned
heuristics that make the output directionally useful while keeping the model
simple and interpretable. Full calibration against measured lap-time deltas is
listed as a future validation step below.

## Assumptions

The model assumes:

- both drivers are compared on the same session and track layout
- telemetry distance alignment is good enough for corner-level comparison
- detected corner segments represent comparable phases for both drivers
- speed deltas are meaningful proxies for local performance loss or gain
- the selected lap data is representative and not dominated by traffic,
  yellow flags, safety-car phases, severe tyre offset, or obvious anomalies

## Known Limitations

The current implementation does not yet model:

- exact elapsed-time integration from distance and speed
- corner length-specific weighting
- acceleration carry down the next straight
- tyre compound, tyre age, fuel load, setup, DRS, ERS deployment, or wind
- traffic, track evolution, weather shifts, or dirty-air effects
- uncertainty bounds for each corner estimate

Because of these limits, `TimeLoss` should be read as an engineering diagnostic
score expressed in seconds, not as a certified lap-time delta.

## Known Biases

The model can overstate or understate loss when:

- a driver takes a different racing line with a different distance profile
- one driver sacrifices entry or apex speed for a stronger exit
- the apex detector splits or merges complex corner sequences incorrectly
- telemetry sampling alignment differs between drivers
- a corner leads into a very short section where exit speed matters less than
  the fixed weight suggests
- a corner leads into a long straight where exit speed may matter even more
  than the fixed weight suggests

These are acceptable tradeoffs for a transparent portfolio-grade heuristic, but
they should be addressed before treating the estimate as a high-fidelity lap
simulation.

## Validation Strategy

The recommended validation target is the real lap-time delta between two
drivers for the selected laps. The model should be evaluated at two levels.

### Lap-Level Validation

1. Select two comparable laps from the same session.
2. Compute the real lap-time delta from FastF1 timing data.
3. Sum all per-corner `TimeLoss` values.
4. Compare the modelled total against the real lap-time delta.
5. Track error metrics such as absolute error and signed bias.

Useful metrics:

```text
lap_error = estimated_total_delta - real_lap_delta
absolute_error = abs(lap_error)
relative_error = absolute_error / abs(real_lap_delta)
```

### Corner-Level Validation

Where distance-aligned telemetry is available, a stronger validation method is
to derive a cumulative delta trace across the lap and compare it with the
corner-level estimate.

Recommended process:

1. Synchronize both drivers by distance.
2. Convert speed from km/h to m/s.
3. Estimate local time increments with `dt = ds / speed`.
4. Compute cumulative delta over distance.
5. Compare the cumulative delta change over each detected corner with the
   heuristic `TimeLoss`.

This creates a reference signal that can be used to tune or replace the fixed
weights.

## Future Improvements

The next engineering step is to move from fixed global weights to validated,
data-driven calibration:

- fit weights against real lap-time deltas across multiple sessions
- learn different weights for slow, medium, and fast corners
- include corner length and following-straight length
- report uncertainty or confidence per corner
- add a validation notebook or automated benchmark dataset
- fail gracefully when validation preconditions are not met

## Driver-DNA Heuristic Scores

The Driver-DNA view reports telemetry-derived heuristic scores on a normalized
0-100 scale. These values describe how strongly a telemetry pattern appears in
the selected lap or session data. They are not objective driver ratings and
should not be interpreted as proof that one driver is universally better than
another.

Current score dimensions:

- `Aggressiveness`: derived from high deceleration events in braking zones.
- `Cornering`: derived from average speed in detected cornering phases.
- `Smoothness`: derived from throttle input stability during transitions.
- `FullThrottle`: derived from the share of samples at near-full throttle.
- `GearWorkload`: derived from total gear-change activity over the lap.

The normalization thresholds are hand-tuned ranges:

```text
Aggressiveness: 95th-percentile deceleration, 50 to 200 km/h/s -> 0 to 100
Cornering:      average cornering-phase speed, 80 to 230 km/h -> 0 to 100
Smoothness:     throttle delta mean, 0.5 to 8.0 -> 100 to 20
FullThrottle:   near-full-throttle sample share, 40% to 85% -> 0 to 100
GearWorkload:   gear-change activity, 30 to 90 shifts -> 0 to 100
```

These ranges are intended to make style dimensions comparable in the UI. They
should be validated against a larger telemetry sample before being used as
stable driver-characterization metrics.

## Interpretation Rule

Use the current `TimeLoss` output to answer:

```text
Where is the performance difference likely coming from?
```

Do not use it alone to claim:

```text
This is the exact measured time lost in this corner.
```

That distinction keeps the analysis honest, defensible, and aligned with the
current implementation.
