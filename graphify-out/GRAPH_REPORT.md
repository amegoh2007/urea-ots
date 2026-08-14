# Graph Report - frontend  (2026-08-14)

## Corpus Check
- 9 files · ~117,039 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 191 nodes · 415 edges · 13 communities (12 shown, 1 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bcf85e9b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.js
- overlays.js
- editor.js
- indicator_dynamics.js
- redraw
- builder.js
- trend.js
- co2_compressor.js
- buildWindow
- popupInit
- backfill
- commitRange
- lv324501_route.js

## God Nodes (most connected - your core abstractions)
1. `redraw()` - 23 edges
2. `buildWindow()` - 17 edges
3. `viewEnd()` - 10 edges
4. `spawnNode()` - 9 edges
5. `editButton()` - 9 edges
6. `popupInit()` - 9 edges
7. `render()` - 8 edges
8. `build()` - 8 edges
9. `rebuild()` - 8 edges
10. `save()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `pan()` --indirect_call--> `backfill()`  [INFERRED]
  frontend/trend.js → frontend/trend.js  _Bridges community 10 → community 4_
- `setSpan()` --indirect_call--> `backfill()`  [INFERRED]
  frontend/trend.js → frontend/trend.js  _Bridges community 10 → community 8_
- `exportPNG()` --calls--> `hms()`  [EXTRACTED]
  frontend/trend.js → frontend/trend.js  _Bridges community 4 → community 11_
- `afterDatasetsDraw()` --calls--> `save()`  [EXTRACTED]
  frontend/trend.js → frontend/trend.js  _Bridges community 9 → community 4_
- `commitRange()` --calls--> `save()`  [EXTRACTED]
  frontend/trend.js → frontend/trend.js  _Bridges community 9 → community 11_

## Import Cycles
- None detected.

## Communities (13 total, 1 thin omitted)

### Community 0 - "app.js"
Cohesion: 0.09
Nodes (32): applyGates(), buildTabs(), COMP_LBL, connect(), ctx, fill(), fillFields(), fmt() (+24 more)

### Community 1 - "overlays.js"
Cohesion: 0.14
Nodes (30): activate(), activeSid(), attach(), boolState(), build(), buildBindMap(), cfg(), closeMenu() (+22 more)

### Community 2 - "editor.js"
Cohesion: 0.20
Nodes (15): btnRedo, btnSave, btnUndo, createSVG(), fromPos, getShapeForType(), init(), pushHistory() (+7 more)

### Community 3 - "indicator_dynamics.js"
Cohesion: 0.20
Nodes (12): baseProfile(), describe(), finiteNonnegative(), profile(), reset(), sample(), seconds(), seed() (+4 more)

### Community 4 - "redraw"
Cohesion: 0.24
Nodes (15): afterDatasetsDraw(), buildChart(), clearRulers(), deskClock(), hms(), maxPanBack(), moveRuler(), norm() (+7 more)

### Community 5 - "builder.js"
Cohesion: 0.40
Nodes (12): autoMigrate(), createLine(), deleteNode(), generateId(), init(), loadLayout(), saveLayout(), selectNode() (+4 more)

### Community 6 - "trend.js"
Cohesion: 0.27
Nodes (11): binds(), bound(), closeMenu(), enqueueAdd(), entry(), flashMain(), injectCSS(), launcherAdd() (+3 more)

### Community 7 - "co2_compressor.js"
Cohesion: 0.39
Nodes (11): boot(), clamp(), ensure(), gp(), hook(), injectCSS(), livePct(), now() (+3 more)

### Community 8 - "buildWindow"
Cohesion: 0.25
Nodes (11): addRuler(), applyCustomSpan(), buildWindow(), flash(), parseSpan(), pxToTime(), removeRuler(), rulerNear() (+3 more)

### Community 9 - "popupInit"
Cohesion: 0.33
Nodes (9): coreAddTag(), coreOpen(), drainPending(), markHist(), popupInit(), removeSlot(), save(), saved() (+1 more)

### Community 10 - "backfill"
Cohesion: 0.40
Nodes (6): backfill(), connectWS(), goLive(), isLive(), noteTime(), onPacket()

### Community 11 - "commitRange"
Cohesion: 0.40
Nodes (6): commitRange(), exportPNG(), renderRows(), stamp(), valueAt(), windowStats()

## Knowledge Gaps
- **21 isolated node(s):** `lastState`, `Health`, `ResetBtn`, `MODE_LETTER`, `FP_MAP` (+16 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `redraw()` connect `redraw` to `trend.js`, `buildWindow`, `popupInit`, `backfill`, `commitRange`?**
  _High betweenness centrality (0.006) - this node is a cross-community bridge._
- **Why does `buildWindow()` connect `buildWindow` to `popupInit`, `commitRange`, `redraw`, `trend.js`?**
  _High betweenness centrality (0.003) - this node is a cross-community bridge._
- **Why does `viewEnd()` connect `redraw` to `buildWindow`, `commitRange`, `trend.js`?**
  _High betweenness centrality (0.001) - this node is a cross-community bridge._
- **What connects `lastState`, `Health`, `ResetBtn` to the rest of the system?**
  _21 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `app.js` be split into smaller, more focused modules?**
  _Cohesion score 0.08858858858858859 - nodes in this community are weakly interconnected._
- **Should `overlays.js` be split into smaller, more focused modules?**
  _Cohesion score 0.13903743315508021 - nodes in this community are weakly interconnected._