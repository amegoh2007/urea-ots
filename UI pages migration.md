# UI page migration — PowerPoint equipment drawing → live HMI screen

How a screen in `Urea Simulation Docs/Equipment Drawing/UI Pages/*.pptx` becomes a live page
in the OTS. All ten screens were produced this way: 321-1 / 322-1 / 322-2 off the 2026-09-02
revision, 324-1 / 324-1b off 2026-09-05, 323-2 / 329-1 off the first 2026-09-15 reissue, and
323-1 / 328-1 / 328-2 off the second.

Read `ui_guidelines.md` first — it is the spec. This file is the procedure.

A slide revision can also *restore* a tag it had previously dropped, or retag a box onto an
instrument the packet already publishes (2026-09-15 did both, twice over). Give
`harvest_binds.py` a pre-migration copy as a second source and the original binding comes back
untouched:

```bash
git show HEAD:frontend/overlays.js > ov_head.js
python <tools>/harvest_binds.py "D:/Work/Urea Simulation/frontend/overlays.js" ov_head.js
```

## The idea in one paragraph

The slide is the drawing *and* the layout. Its background — vessels, lines, valve bodies,
equipment labels — is rendered once to a PNG and never redrawn in code. Every shape that must
show live data is **deleted from that PNG** and replaced by an overlay `div` positioned at the
deleted shape's own centre, sized from its own extent, rotated and mirrored by its own
transform. So an overlay cannot drift off its symbol: it lands in the hole the symbol left.

The deck is self-describing. PowerPoint comments (`ppt/comments/modernComment_*.xml`) bind text
to a shape id, and the drawings use them as instructions:

| comment on a shape | becomes |
|---|---|
| `LIC-323501 dynamic vertical display bar` | `t:'bar'` level bargraph bound to that tag |
| `329P006A` | `t:'pump'` icon, A duty / B standby |
| `XV-322915` | `t:'xv'` block valve, `xv_toggle` on click |
| `OVERRIDE TO CLOSE XV-322915 …` | `t:'ovrd'` pushbutton |
| `LINK TO PAGE 324-1B` | `t:'nav'` screen-jump hotspot |
| `Replace by MASTER SP Editable value` | the editable master-setpoint box |

Anything else whose text matches a DCS tag (`TT-323001`, `FFIC-335406`, `LV-324501A`, …) becomes
an indicator: `t:'avalve'` for `PV-`/`LV-`/`FV-`/`TV-`, otherwise `t:'ind'`.

## Coordinates

Slides are `12192000 × 6858000` EMU. The stage is `1366 × 720`, so the mapping is
**anisotropic**: `sx = 1366/12192000` across, `sy = 720/6858000` down, ratio
`SLIDE_RX = sx/sy = 1.06719`. That squash is applied in three places and they must agree:

1. `build_overlays.py` maps EMU centres to stage pixels with `sx`/`sy`.
2. `render_slides.ps1` exports the PNG at 1366×720 from a 16:9 slide — the same squash.
3. `sizeIcon()` in `overlays.js` undoes it for rotated icons: the `<img>` is sized
   `(w/SLIDE_RX) × h` and carries `transform: scaleX(SLIDE_RX) rotate(θ) scale(±1,±1)`.
   Right-most applies first, which is PowerPoint's order — mirror inside the box, then rotate
   the box, then unsquash. Exact for any θ, and identity at θ = 0 with no flip.

## Procedure

Work in a scratch directory; `<tools>` is `tools/ui_migration`.

```bash
python <tools>/parse_slide.py 323-1 323-2 324-1        # unzip + shape inventory -> <name>_shapes.json
python <tools>/harvest_binds.py                        # existing overlays.js -> binds_all.json
python <tools>/build_overlays.py                       # shapes + binds -> ov_build.json
python <tools>/emit_overlays.py                        # ov_build.json -> ov_blocks.txt (paste-ready JS)
python <tools>/strip_slides.py                         # delete those shapes -> stripped/<name>.pptx
powershell -File <tools>/render_slides.ps1 323-1 323-2 324-1
```

Then:

1. Copy `stripped/screen-*.png` into `frontend/img/`.
2. Paste the blocks from `ov_blocks.txt` over the matching `'screen-…': [ … ]` entries in
   `frontend/overlays.js`. Edit the slide list at the bottom of `build_overlays.py` and
   `emit_overlays.py` to match what you are migrating; `emit_overlays.py` writes them in the
   order they appear in `overlays.js` so the patch is a straight block-for-block swap.
3. Bump `LSK` / `MK` in `overlays.js` and put the re-seeded screen ids in `REMAPPED`. Element
   keys are derived from the tag, so a re-seed invalidates stored drag positions on those
   screens — and only those; `carryOver()` keeps the rest.
4. Verify (below), then update `handoff.md` §8.

Bindings are never retyped. `harvest_binds.py` reads the current `overlays.js` by brace depth
(records span lines — a line-wise regex silently drops `mode:` on a continuation) and carries
`bind`, `u`, `dec`, `mode`, `cas`, `face`, `fp`, `route` and the physics `note` across by tag.
A tag the new drawing introduces needs one row in `build_overlays.py`'s `EXTRA` table.

## The four decision tables in `build_overlays.py`

Every departure from "the slide is right" is one row in a table, so a re-seed cannot silently
undo it and a reviewer can see the whole list at a glance:

- `EXTRA` — bindings for tags the harvest could not supply. A *retag* lands here too when the
  packet publishes the same number under two leaves: 323-1's `TT-323103` became `TT-323008`, and
  `RECIRC_323.D002` carries `round(s.r323_d002_T, 1)` as both `.T_C` and `.TI_323008`, so the row
  pins the tag-named leaf and records why either would have worked.
- `RETAG` — the slide prints the wrong tag (`{slide: {shape id: correct tag}}`). Currently
  empty: its one entry covered 328-1 shape 214, which printed `LIC-328503` on the 328C003 leg
  whose own bargraph comment read `LIC-328504`, and the 2026-09-15 reissue fixed the drawing.
  Delete an entry once the deck corrects it — a stale row silently overrides a now-correct
  label. Check this table on every re-seed, not only when a new typo turns up.
- `ADD_PUMP` — pump icons the deck forgot to annotate (`{slide: {shape id: pump tag}}`).
- `NUDGE` — the only reason to move a box off its slide centre. An `.ov.ind` is sized by its
  *value*, not by the label it replaced, so a few render wider than the hole and clip a
  neighbour. Three on 323-2; each row records what it was clipping.

## Verification — measure it, do not eyeball it

With the app running (`preview_start` on the `ots` config), in the page:

- **Overlay vs overlay.** For each screen, `getBoundingClientRect()` every `.ov` and test all
  pairs. This must be **zero** on every screen. Nav hotspots count: they are transparent, so an
  overlap steals clicks rather than showing.
- **Overlay vs its own footprint.** Dump each overlay's original shape box in the *emitted*
  order and compare. Anything protruding is a box wider than its label — check what the
  protrusion lands on before accepting it.
- **Overlay vs surviving background text.** Test against every text-bearing shape that was not
  stripped. Expect hits where the drawing itself puts a label on a symbol (the `A`/`B` letters
  printed over pump icons); investigate anything else.
- Then `read_console_messages` for errors and a screenshot per page.

Run `backend/test_trend_coverage.py`, `backend/test_328d003_compartments.py`,
`backend/test_ui_hand_valve_bindings.py` and `frontend/test_indicator_dynamics.js`. Three of
those carry counts that follow the drawings rather than the code (`BOUND_TAG_FLOOR`, the
`t:'ind'` sanity floor, the avalve floor, plus the white-frame ceiling). When a drawing revision
legitimately moves one, move it **and write the accounting into the comment** — those comments
are the only record of what the deck stopped showing, and of what a later revision gave back.

## What the deck cannot give you

- **Stream hotspots.** Nothing in the slide says which drawn polyline is which process stream,
  so `t:'strm'` elements are placed by hand against the P&ID or not at all. The seven screens
  migrated in September have none.
- **Pump commandability.** A pump icon is only clickable if the backend models that machine.
  The rest render A running / B stopped (`def:false`) and are inert.
- **Faceplate routing for panel readouts.** A box labelled `FFIC-329401 SP` is a readout, not a
  controller: sending `controller_set` with that id reaches `handle_cmd` as an unknown tag and
  is silently discarded. Leave such boxes read-only unless you add a bespoke route.
