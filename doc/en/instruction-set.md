# ASSAM v1 Instruction Set Specification

Language: [日本語](../jp/命令セット仕様.md) | English

This document specifies the syntax, instructions, validation rules, and error behavior of ASSAM v1 as executed by the Python VM.

## Profiles

- `core` is a small low-level instruction layer intended for mechanical mapping to other targets.
- `full` includes Core instructions plus ASSAM VM conveniences and terminal operations.
- `Push`, `Pop`, and terminal operations are available only in `full`; terminal operations are not Core instructions.
- The VM and analyzer accept an explicit profile. If omitted, they use the JSON IR profile marker. Legacy programs without a marker are treated as `full`.
- The [instruction registry](../../assam/data/instruction_registry.json) is the shared source for opcode names and aliases, operand forms, handlers, register effects, guest-memory effects, trap conditions, and control flow. Parser, C input translator, VM, and analyzer consume it. Each Core opcode has a namespaced `target_mapping_id` for future mapping tables; the ID does not mean a mapping exists or is complete. `read_operands` and `write_operands` refer to operand positions. `data_memory_effects` covers only guest-addressable data memory, not VM-internal stacks or the terminal bus. Core integer data operands are listed under `integer_parameters`; result positions are listed under `write_operands`. Width and signedness remain `not_decided`, so this metadata does not define execution semantics. The JSON `schema_version` versions the registry format, not the Core profile, which remains Draft.

### Instructions by profile

The current Python implementation accepts these Core instructions: `Move`, `Load`, `Store`, `Add`, `Subtract`, `Multiply`, `Divide`, `Modulo`, `And`, `Or`, `Xor`, `Not`, `ShiftLeft`, `ShiftRight`, `Compare`, `Jump`, `JumpEqual`, `JumpNotEqual`, `Call`, `Return`, and `Halt`. This is an implementation list, not a final Core specification.

`full` additionally accepts `Push`, `Pop`, and virtual-terminal operations. The CLI's `--profile core` validates conformance to this boundary. Architecture translation, integer width, and calling convention still require separate specification.

## JSON IR profile marker

- The [program-ir-v1.schema.json](../../assam/data/program-ir-v1.schema.json) describes the overall JSON IR structure. Existing JSON without a profile marker remains valid.
- The schema checks structure. `InstructionSet` separately validates opcode and operand meaning, as well as label references.
- `json --profile core` validates a program as Core and adds a top-level `profile` object to the JSON IR.
- The marker records the profile name, version, and instruction-registry schema version. The current version string `draft` is not a stability guarantee.
- Current marker: `{"profile":{"name":"Assam Core","version":"draft","registry_schema_version":2}}`.
- The marker schema is [assam-core-profile-draft.schema.json](../../assam/data/assam-core-profile-draft.schema.json).
- The shared opcode/operand and effects definition is [instruction_registry.json](../../assam/data/instruction_registry.json), described by [instruction-registry-v2.schema.json](../../assam/data/instruction-registry-v2.schema.json).
- `run` and `analyze` use the marked profile by default and reject an explicit conflicting profile.
- For backward compatibility, JSON IR without a marker is treated as `full`.

## Basic syntax

- Write one instruction per line. Opcode names are case-insensitive.
- Separate operands with whitespace or commas. Text after `;` is a comment.
- Labels use the form `name:`; branches refer to a label by name.
- Integers are decimal or `0x` hexadecimal. Registers range from `r0` to `r15`.
- Operand positions that accept registers also accept immediate values or registers. A string consisting of `r` followed by digits is interpreted as a register.
- `Compare` writes `1` when values are equal and `0` otherwise.
- `Divide` rounds integer division toward zero. `Modulo` is defined as `x - Divide(x, y) * y`.
- `Load` and `Store` use sparse VM memory. `Load` returns `0` for an address that has not been written.
- The VM validates opcodes, labels, operand counts and forms, register range, and branch targets before execution. Invalid programs are rejected with `ValueError`.
- `trap_conditions` records instruction-local conditions observed in the current Python VM: division by zero, negative shift counts, and call-stack underflow. Full-only `Pop` records data-stack underflow. This does not establish normative Draft Core trap semantics; terminal-bus and host/environment errors are excluded.
- Runtime traps and terminal communication errors are reported as `VMError` with the instruction location.

## Instruction list

| Instruction | Operands | Behavior |
|---|---|---|
| Move | `register, value` | Assign a value to a register |
| Load | `register, address` | Read from memory |
| Store | `address, value` | Write to memory |
| Add / Subtract / Multiply / Divide / Modulo | `register, integer, integer` | Integer arithmetic |
| And / Or / Xor | `register, integer, integer` | Bitwise operation |
| Not | `register, integer` | Bitwise inversion |
| ShiftLeft / ShiftRight | `register, integer, integer` | Shift an integer by the specified count |
| Compare | `register, value, value` | Equality comparison |
| Jump | `target` | Unconditional branch |
| JumpEqual / JumpNotEqual | `target, value, value` | Branch on equality / inequality |
| Call / Return | `target` / no operands | Call / return |
| Push / Pop | `value` / `register` | Data-stack operation |
| Halt | no operands | Stop the VM |
| CreateTerminal / DestroyTerminal | `name` | Create / destroy a virtual terminal |
| ConnectTerminal / DisconnectTerminal | `name, name` | Change terminal connections |
| Send | `sender, recipient, value` | Send a message to a connected terminal |
| Broadcast | `sender, value` | Send to all connected terminals |

`Push`, `Pop`, and all terminal operations starting with `CreateTerminal` are Full-only.

`mov`, `j`, `je`, `jne`, `ret`, `stop`, `shl`, and `shr` are aliases.

## Error rules

- Unknown instructions, wrong operand counts, out-of-range registers, and undefined labels are rejected when the VM is created.
- Include the instruction position and source line in diagnostics when available.
- Runtime errors are raised as `VMError` containing the instruction pointer and instruction.
- Runtime errors from terminal instructions are converted to `VMError` with the relevant instruction location.
- An omitted `trap_conditions` field means the registry does not currently classify an instruction-local trap for that instruction. Execution limits such as the step limit are environmental constraints, not instruction traps.
