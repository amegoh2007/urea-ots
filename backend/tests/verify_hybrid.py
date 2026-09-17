from backend.main import step_sim

try:
    state = step_sim(1.0)
    print("step_sim() executed successfully in Hybrid SM Mode.")
    print("Scrubber output keys:", [k for k in state if "322e003" in k.lower() or "ccw" in k.lower() or "vent" in k.lower()])
except Exception as e:
    import traceback
    traceback.print_exc()
    print("Error during step_sim()")
