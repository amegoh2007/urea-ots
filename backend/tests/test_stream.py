from backend.core.stream import Stream

def test_stream_dirty_flag():
    s = Stream(name="S1")
    flag_triggered = False
    
    def callback(stream):
        nonlocal flag_triggered
        flag_triggered = True
        
    s.subscribe(callback)
    s.set_state(T=150.0, P=140.0)
    
    assert s.is_dirty is True
    assert flag_triggered is True
