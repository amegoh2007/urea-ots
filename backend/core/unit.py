from typing import List
from core.stream import Stream

class UnitOperation:
    def __init__(self, name: str, inputs: List[Stream], outputs: List[Stream]):
        self.name = name
        self.inputs = inputs
        self.outputs = outputs
        
        for stream in self.inputs:
            stream.subscribe(self._on_input_changed)
            
    def _on_input_changed(self, stream: Stream):
        # In the Flowsheet topology, we rely on the central solver loop
        # rather than immediate reactive recursion to prevent infinite loops
        # and stack overflows on recycles.
        pass
            
    def solve(self):
        raise NotImplementedError("Subclasses must implement MESH equations")
