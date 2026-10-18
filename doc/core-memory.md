# Core draft.2: bounded guest memory

Status: **experimental subset**, not stable Core v1 or architecture admission.
Profile: `assam-core/v1-draft.2`. Depends on the draft.1 bootstrap in PR #16.
Related: #2 (registry), #3 (semantics), #4 (translation), #13 (CI).

## Version and consumer boundary

Draft.1 remains selectable through `core.Profile` and rejects all memory opcodes.
Its original `core/registry.json`, corpus, arithmetic semantics, and JSON result
shape are unchanged. The earlier `doc/core-bootstrap.md` describes that profile.

Draft.2 inherits those 22 opcodes and adds only 11 memory opcodes. The checked-in
extension `core/registry-memory.json` specifies `extends`, widths, signedness,
operand roles, effects, memory layout, and the bounds trap. It does not copy the
arithmetic table or embed executable code. `SchemaForProfile` emits the resolved
registry; `Schema()` retains the exact draft.1 bytes. Overrides, unknown effects,
invalid memory widths, operand layouts, and incompatible contracts are rejected.

Go and the Python development oracle consume these shared definitions, but use
independent access implementations: Go checks subtraction before indexing and
assembles bytes; Python uses arbitrary-precision range arithmetic and explicit
little-endian byte conversion. A matching result is a test, not a safety proof.

The ordinary-opcode architecture mapping gate is STILL outstanding. Neither
profile accepts `assam-core/v1`. No x64/ARM64/RISC-V mapping is claimed complete.
Bitlang-VM has not been modified or pinned to this draft by this change.

## Address space and lifetime

Guest memory is a finite contiguous byte array with unsigned **64-bit** guest
addresses. Valid bytes are `[0, size)`. These values are not Go pointers, JVM
references, Python object IDs, or host-width integers. Address zero is a valid
byte when size is nonzero; it has no implicit null-pointer semantics here.

The embedding caller supplies the complete initial image to `RunWithMemory`.
That image is copied before execution. Registers/PC start fresh as in draft.1.
The returned `MemoryExecution.Memory` owns the final image, including writes
completed before halt, trap, or step limit; it does not alias the input or any
other run. Concurrent calls may share an immutable Program and read-only image.
The caller must not mutate the input slice while it is being copied.

This bootstrap caps each memory image at **16 MiB**. The cap is a host resource
policy, not a reduction of the 64-bit guest address contract. An oversized image
or a program not validated as draft.2 is a configuration error before execution,
not a guest bounds trap. An empty image is valid: every load/store then traps.
The cap does not guarantee survival of host-wide memory exhaustion or provide
OS process isolation. No FFI, unsafe pointers, allocation/free opcodes, memory
mapping, guest concurrency, permissions, or host I/O are added.

The CLI allocates `-memory-bytes N` zero-filled bytes (default zero) and optionally
copies `-memory-hex HEX` into their prefix. Oversized, malformed, or truncated hex
images are rejected before execution. Unprovided bytes **inside** the allocation
are explicitly zero-initialized; reads outside it never silently return zero.

## Instruction contract

There is deliberately no implicit base-plus-offset addressing. Compute the
address with existing Core instructions, then use the address register directly.
Any prior `add` retains its existing modulo-2^64 behavior; load/store do not turn
that arithmetic into checked addition or pointer-provenance validation.

| Opcode | Operands | Transfer |
|---|---|---|
| load8u / load8s | rd, ra | Read 1 byte, zero/sign-extend to 64 bits. |
| load16u / load16s | rd, ra | Read 2 bytes, zero/sign-extend. |
| load32u / load32s | rd, ra | Read 4 bytes, zero/sign-extend. |
| load64 | rd, ra | Read 8 bytes as the complete 64-bit bit pattern. |
| store8 / store16 / store32 / store64 | ra, rs | Write the low 1/2/4/8 bytes of rs. |

All multi-byte transfers are **little-endian**; unaligned access is allowed.
There is no distinct signed 64-bit load because the resulting 64-bit pattern
would be identical. Each instruction reads source registers before writing its
destination, so `load8u r1, r1` and `store8 r1, r1` have unambiguous behavior.

The entire transfer must fit. For width W and guest address A, Go first checks
`W <= size`, then `A <= size - W`; it does not compute a wrapping `A + W`.
Only then is the address converted to a host index. This applies on 32-bit hosts
too. Width is validated as 1, 2, 4 or 8 through the registry.

On failure: `status=trap`, `code=memory_out_of_bounds`; PC/source line identify
the faulting instruction; the attempted instruction consumes one step. A load
leaves its destination unchanged, including when destination is r0. A store
changes **no bytes**, not even a valid prefix. Earlier completed instructions
are NOT rolled back. r0-destination loads still perform access validation and
can trap; only a successful value write is discarded.

The draft.1 budget/check ordering is unchanged: budget, PC, instruction attempt.
An out-of-bounds access on the final allowed attempt reports its bounds trap;
a zero budget prevents even that access. A completed store at the last allowed
step is observable in the memory snapshot when the next check reports step_limit.

## API and output

```go
func execute(source string, initialBytes []byte) (core.MemoryExecution, error) {
    program, err := core.Parse(source, core.MemoryProfile)
    if err != nil {
        return core.MemoryExecution{}, err
    }
    return core.RunWithMemory(program, 1000, initialBytes)
}
// Successful configuration returns Result plus an independently owned Memory.
// Guest traps are in Result; malformed input/configuration returns an error.
```

`core.Run(program, budget)` retains its signature and has zero bytes of memory;
a draft.2 program using load/store therefore bounds-traps through that API.
`RunWithMemory` requires a validated draft.2 program even for an empty image.

```sh
go run ./cmd/assam-core -profile assam-core/v1-draft.2 -memory-bytes 9 -dump-memory examples/core/memory.assam
```

The CLI keeps the previous JSON fields and exit codes: 0 for halt, 1 for guest
trap/step limit, 2 for invalid input/configuration/output error. The new
`memory_hex` field is emitted **only** with `-dump-memory`, as lowercase hex in
increasing address order. The full bounded image is included only when requested.
Memory flags are rejected with draft.1 and with `-canonical` rather than ignored.

## Verification and remaining work

The shared memory corpus has 32 explicit result/byte-image cases and 10 malformed
programs. It covers every added opcode, signed/unsigned loads, endianness,
unaligned access, register aliasing, zero-sized memory, huge addresses, atomic
failed stores, r0, branch-skipped stores, and step-budget boundaries.

Both languages also compare the complete register state and final bytes for 250
seeded generated programs and an all-width boundary grid. Every original valid
arithmetic fixture is replayed under both profiles. Go tests cover input/output
ownership, independent concurrent runs, resource limits, registry corruption,
and fuzzed memory accesses. CI retains the Ubuntu/Windows/macOS matrix and adds
memory smoke, memory fuzzing, and an Ubuntu 32-bit regression step.

Still pending: calling-convention primitives, jump-and-link/indirect-jump,
allocation/runtime-helper ABI, common validated program IR, complete schema and
architecture mapping coverage, Bitlang-VM dependency pin/integration, public
Python Core API, Java/Rust VMs, and the separate legacy Full audit fixes.
