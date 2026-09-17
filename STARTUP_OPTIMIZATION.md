# Startup Time Optimization Guide

## Understanding Startup Time

The backend takes ~20-25 seconds to start. This is **normal** and consists of:

1. **Python imports** (~22s): Loading all physics modules
   - `reactor.py`, `hp_recycle.py`, `thermo_urea_hp.py`, etc.
   - This cannot be avoided - it's the simulation engine loading

2. **Boot pin cache** (~0.5s with cache hit, ~20s with cache miss):
   - Cache HIT: Design constants restored instantly
   - Cache MISS: Full 21k-tick settle runs to calculate design constants
   - Cache invalidates ONLY when physics source files change

## When to Restart the Backend

**❌ DON'T restart after editing:**
- `frontend/app.js`
- `frontend/index.html`
- `frontend/*.css`
- Any other frontend file

**✅ DO restart after editing:**
- `backend/main.py` (API handlers, physics)
- `backend/reactor.py`, `steam_system.py`, etc. (physics modules)
- `backend/controllers.py` (control logic)

## Fast Development Workflow

### Frontend Changes (app.js, index.html)
1. Edit the file
2. **Just refresh the browser** (Ctrl+R or F5)
3. Done! The backend serves static files - no restart needed

### Backend API Changes (main.py handlers only)
1. Edit the file
2. Stop the backend (close the "Urea Simulation Backend" window)
3. Run `launch.bat` again (~22s)
4. The boot pin cache will HIT (instant constant restore)

### Backend Physics Changes (reactor.py, thermo_*, etc.)
1. Edit the file
2. Stop the backend
3. Run `launch.bat` again (~40s total)
4. The boot pin cache will MISS (20s settle + 22s imports)
5. This is expected - physics changes require full recalibration

## Cache Status

Check if your cache is valid:

```bash
cd backend
python -c "
import hashlib, json, os
files = ['main.py', 'steam_system.py', 'reactor.py', 'thermo_urea_hp.py', 
         'hp_recycle.py', 'core/valve.py', 'core/scrubber.py', 'controllers.py',
         'thermo_extended_uniquac.py', 'consequence.py', 'vle_nh3co2h2o.py']
h = hashlib.sha256()
for fn in files:
    with open(fn, 'rb') as f: h.update(f.read())
with open('.boot_pin_cache.json') as f:
    print('Cache', 'VALID ✓' if json.load(f)['key'] == h.hexdigest() else 'INVALID ✗')
"
```

## Troubleshooting

### "Cache hit but still slow"
- Normal! Cache only skips the 20s settle, not the 22s import time
- Solution: Keep the backend running when editing frontend files

### "Cache miss after frontend edit"
- Something touched a physics file (maybe git, IDE, or file watcher)
- Solution: Check `git status backend/` to see what changed
- If nothing changed, the cache file itself might be corrupt - delete it and restart once

### "Every startup takes 40+ seconds"
- Cache is missing or constantly invalidating
- Check if an IDE plugin is auto-formatting physics files on save
- Check if a file watcher is touching the files
- Solution: Disable auto-format for the backend/ directory

## Future Optimization Ideas

If startup time becomes critical:

1. **Split non-physics code**: Move API handlers to a separate file not tracked by cache
2. **Lazy imports**: Defer physics imports until first simulation step
3. **Precompiled bytecode**: Use `python -m compileall backend/` to cache .pyc files
4. **Keep-alive mode**: Add a "reload physics" endpoint instead of full restart

For now, the fastest workflow is: **don't restart the backend for frontend changes**.
