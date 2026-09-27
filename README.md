# ASSAM

ASSAM (Assembly Abstract Machine) のPythonリファレンス実装です。

現在は、テキスト構文、JSON IR、基本VM、デバッガー、仮想端末バスを実装しています。

```python
from assam import VM, parse_program
program = parse_program("Move r0 2\nAdd r1 r0 3\nHalt")
print(VM(program).run()["r1"])
```

CLI:

```text
python -m assam.cli run program.assam
python -m assam.cli json program.assam -o program.json
python -m assam.cli run program.json --json
```