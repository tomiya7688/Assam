"""Small debugger facade for inspecting an ASSAM VM."""
from dataclasses import dataclass
@dataclass(frozen=True)
class DebugState:
    ip:int; halted:bool; registers:dict; memory:dict; stack:tuple; call_stack:tuple
class Debugger:
    def __init__(self, vm): self.vm=vm; self.breakpoints=set()
    def add_breakpoint(self, instruction_index):
        if instruction_index<0: raise ValueError("breakpoint must not be negative")
        self.breakpoints.add(instruction_index)
    def remove_breakpoint(self, instruction_index): self.breakpoints.discard(instruction_index)
    def clear_breakpoints(self): self.breakpoints.clear()
    def state(self): return DebugState(self.vm.ip,self.vm.halted,dict(self.vm.registers),dict(self.vm.memory),tuple(self.vm.stack),tuple(self.vm.call_stack))
    def step(self): self.vm.step(); return self.state()
    def continue_execution(self, *, max_steps=100000):
        steps=0
        while not self.vm.halted:
            if steps and self.vm.ip in self.breakpoints: break
            if steps>=max_steps: raise RuntimeError(f"debug step limit exceeded: {max_steps}")
            self.vm.step(); steps+=1
        return self.state()