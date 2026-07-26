import os, sys, time, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
pkt = main.step_sim(0.1)
N = 500
t = time.perf_counter()
for _ in range(N): m = json.dumps(pkt)
enc = (time.perf_counter()-t)/N
print("json.dumps(packet) mean_ms = %.3f  bytes=%d" % (1000*enc, len(m.encode())))
print("push_task @10 Hz single client: %.2f %% of one core just serialising" % (100*enc*10))
print("10 clients (dumps once, send x10): still %.2f %% + 10 sends" % (100*enc*10))

# event-loop blocking budget
for _ in range(20): main.step_sim(0.5)
t = time.perf_counter()
for _ in range(200): main.step_sim(0.5)
big = (time.perf_counter()-t)/200
print("\nSLOW  tick: step_sim(0.1) blocks loop; FAST tick: 12x step_sim(0.5) = %.1f ms contiguous block"
      % (1000*big*12))
print("-> ws.receive_text() for operator commands cannot be serviced during that block")
print("-> asyncio.sleep(DT=0.1) is a FIXED sleep AFTER the work, so real period = 0.1 + work")
print("   SLOW real period ~= %.1f ms (%.2f Hz),  FAST ~= %.1f ms (%.2f Hz)"
      % (1000*(0.1+big), 1/(0.1+big), 1000*(0.1+big*12), 1/(0.1+big*12)))
print("   => FAST advances %.1f sim-s per real-s, NOT the advertised 60x (%.0f%% of nominal)"
      % (60*0.1/(0.1+big*12), 100*(0.1/(0.1+big*12))))
