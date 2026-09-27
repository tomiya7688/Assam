import sys
sys.path.insert(0, ".")
from assam import VM, parse_program
from assam.generator import generate, load
from assam.debugger import Debugger
from assam.terminal import BasicTerminal, TerminalBus

def test_json_and_vm():
    p=parse_program("Move r0 2\nAdd r1 r0 3\nHalt"); assert VM(load(generate(p))).run()["r1"]==5

def test_memory_stack_and_call():
    p=parse_program("Move r0 4\nStore 100 r0\nLoad r1 100\nCall double\nHalt\ndouble:\nAdd r1 r1 r1\nReturn")
    v=VM(p); assert v.run()["r1"]==8 and v.memory[100]==4 and not v.call_stack

def test_debugger():
    d=Debugger(VM(parse_program("Move r0 1\nAdd r0 r0 2\nHalt"))); d.add_breakpoint(1); assert d.continue_execution().ip==1; assert d.continue_execution().halted

def test_terminal_bus():
    b=TerminalBus(); a,c=BasicTerminal("a"),BasicTerminal("c"); b.register(a); b.register(c); b.connect("a","c"); b.send("a","c","hello"); assert c.inbox[0].payload=="hello"