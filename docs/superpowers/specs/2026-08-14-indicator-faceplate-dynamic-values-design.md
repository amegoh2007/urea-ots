# Indicator Faceplate Dynamic Values Design

## Goal

Give every clickable process indicator a controller-style faceplate. The faceplate must show the indicator's current simulated value after process/indicator dynamics and engineering-unit conversion.

## Display rules

- Numeric values use exactly three decimal places.
- Discrete values preserve their process text exactly, including `ON` and `LOW`.
- Controller faceplates retain their existing SP, output, and mode controls; their PV uses the same live-value source and formatting as indicator faceplates.
- Non-controller indicators use the controller card's header, typography, row spacing, and close controls, but show only meaningful read-only fields: PV and engineering unit.
- Existing specialized control faceplates remain specialized while adopting the shared live PV formatting.

## Architecture

Add a small browser/Node-compatible `IndicatorFaceplate` module. It owns a live-value registry keyed by instrument tag and exposes:

- publication of the final displayed value and unit;
- lookup of the latest value by tag;
- one formatter that renders numeric values to three decimals and leaves strings unchanged.

Both indicator rendering paths publish after applying FOPDT dynamics and unit conversion:

1. legacy SVG `.pi` indicators in `app.js`;
2. generated overlay indicators in `overlays.js`.

This avoids recomputing dynamics in a faceplate and guarantees the drawing and faceplate refer to the same simulated sample.

## Interaction flow

1. A simulation packet updates the process display.
2. Each rendered indicator publishes its final value to the registry.
3. Clicking a non-controller indicator opens the generic indicator faceplate for that tag.
4. Clicking a controller opens its existing controller faceplate.
5. While any faceplate is open, subsequent packets refresh its PV from the registry.

## Edge cases

- If no current sample is available, show an em dash rather than stale or fabricated data.
- Digital values are never coerced to numbers.
- Missing engineering units render as an empty unit field.
- Existing alarm colors and click targets remain unchanged.

## Verification

- Unit tests cover three-decimal numeric formatting, unchanged digital text, and registry updates.
- Integration assertions cover module load order, publication from both rendering paths, generic indicator click handling, and controller PV use of the shared formatter.
- JavaScript syntax checks and the existing indicator-dynamics suite must pass.
