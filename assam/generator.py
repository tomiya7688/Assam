from pathlib import Path
from .ir import Program
def generate(program, *, indent=2): return program.to_json(indent=indent)
def load(source): return Program.from_json(source)
def write(program, path, *, indent=2): Path(path).write_text(generate(program,indent=indent),encoding="utf-8")
def read(path): return load(Path(path).read_text(encoding="utf-8"))