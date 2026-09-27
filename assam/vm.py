"""Reference VM for the initial ASSAM instruction subset."""
from .terminal import BasicTerminal, TerminalBus
class VMError(RuntimeError): pass
class VM:
    def __init__(self, program, *, register_count=16):
        self.program=program; self.registers={f"r{i}":0 for i in range(register_count)}; self.memory={}; self.stack=[]; self.call_stack=[]; self.bus=TerminalBus(); self.ip=0; self.halted=False
    def _value(self, x): return self.registers[x] if isinstance(x,str) and x in self.registers else x
    def _reg(self, x):
        if not isinstance(x,str) or x not in self.registers: raise VMError(f"invalid register: {x!r}")
        return x
    def _target(self, x):
        if isinstance(x,str) and x in self.program.labels: return self.program.labels[x]
        if isinstance(x,int): return x
        raise VMError(f"invalid jump target: {x!r}")
    def step(self):
        if self.halted: return
        if not 0 <= self.ip < len(self.program.instructions): raise VMError(f"instruction pointer out of range: {self.ip}")
        ins=self.program.instructions[self.ip]; op,a,nxt=ins.opcode.lower(),ins.operands,self.ip+1
        try:
            if op in {"move","mov"}: self.registers[self._reg(a[0])]=self._value(a[1])
            elif op=="createterminal": self.bus.register(BasicTerminal(self._value(a[0])))
            elif op=="destroyterminal": self.bus.unregister(self._value(a[0]))
            elif op=="connectterminal": self.bus.connect(self._value(a[0]),self._value(a[1]))
            elif op=="disconnectterminal": self.bus.disconnect(self._value(a[0]),self._value(a[1]))
            elif op=="send": self.bus.send(self._value(a[0]),self._value(a[1]),self._value(a[2]))
            elif op=="broadcast": self.bus.broadcast(self._value(a[0]),self._value(a[1]))
            elif op=="load": self.registers[self._reg(a[0])]=self.memory.get(self._value(a[1]),0)
            elif op=="store": self.memory[self._value(a[0])]=self._value(a[1])
            elif op in {"add","subtract","multiply","divide","modulo"}:
                d,x,y=self._reg(a[0]),self._value(a[1]),self._value(a[2]); self.registers[d]={"add":x+y,"subtract":x-y,"multiply":x*y,"divide":x//y,"modulo":x%y}[op]
            elif op in {"and","or","xor"}:
                d,x,y=self._reg(a[0]),self._value(a[1]),self._value(a[2]); self.registers[d]={"and":x&y,"or":x|y,"xor":x^y}[op]
            elif op=="not": self.registers[self._reg(a[0])]=~self._value(a[1])
            elif op in {"shiftleft","shl","shiftright","shr"}:
                d,x,n=self._reg(a[0]),self._value(a[1]),self._value(a[2]); self.registers[d]=x<<n if op in {"shiftleft","shl"} else x>>n
            elif op=="compare": self.registers[self._reg(a[0])]=int(self._value(a[1])==self._value(a[2]))
            elif op=="push": self.stack.append(self._value(a[0]))
            elif op=="pop":
                if not self.stack: raise VMError("stack underflow")
                self.registers[self._reg(a[0])]=self.stack.pop()
            elif op=="call": self.call_stack.append(self.ip+1); nxt=self._target(a[0])
            elif op in {"return","ret"}:
                if not self.call_stack: raise VMError("call stack underflow")
                nxt=self.call_stack.pop()
            elif op in {"jump","j"}: nxt=self._target(a[0])
            elif op in {"jumpequal","je"} and self._value(a[1])==self._value(a[2]): nxt=self._target(a[0])
            elif op in {"jumpnotequal","jne"} and self._value(a[1])!=self._value(a[2]): nxt=self._target(a[0])
            elif op in {"halt","stop"}: self.halted=True; return
            else: raise VMError(f"unknown or malformed instruction: {ins}")
        except (IndexError,TypeError,ValueError,ZeroDivisionError) as exc: raise VMError(f"invalid instruction at {self.ip}: {ins}") from exc
        self.ip=nxt
    def run(self, *, max_steps=100000):
        for _ in range(max_steps):
            if self.halted: return dict(self.registers)
            self.step()
        raise VMError(f"step limit exceeded: {max_steps}")