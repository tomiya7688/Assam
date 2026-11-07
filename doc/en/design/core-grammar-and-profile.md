# Core grammar and profile contract

Language: [日本語](../../jp/設計/Core文法とprofile契約.md) | English

Target issues: #1 (grammar, profile/version), #10 (operand types, string preservation). Decisions: DEC-01, DEC-11, DEC-17, PRO-01, PRO-02.

## 1. Two entry points and one IR

```text
Full text  --(Full parser)------\
                                 +--> Program(IR, typed operands) --> validation (per profile) --> VM / translation
Core text  --(Core parser)------/
JSON IR ---(loader)------------/
```

- **Full parser**: accepts the current free-form syntax (PascalCase, case-insensitive, whitespace/comma, aliases, quoted strings) with backward compatibility.
- **Core parser**: a strict parser that accepts only the canonical form. Make it a **separate class in a separate file**. Do not loosen the Full parser or reuse it with branching.
- Both produce the same `Program` (typed operands). Subsequent validation, execution, and translation take the IR as input and do not depend on the text form.

## 2. Typed operands (#10)

Currently operands are "string/integer", so `"r1"` cannot be distinguished as string or register. Split them into these four kinds.

| kind        | Example (text)           | IR representation                 | Notes                                                          |
| ----------- | ------------------------ | --------------------------------- | -------------------------------------------------------------- |
| `register`  | `r5`                     | `{"kind":"register","index":5}`   | Core: `r0`-`r31`. Full is also widened to `r0`-`r31` (WP-B1)   |
| `immediate` | `42`, `0x2A`, `-1`       | `{"kind":"immediate","value":42}` | Decimal/`0x`. Signed. Range is per instruction (see semantics) |
| `symbol`    | `loop` (label reference) | `{"kind":"symbol","name":"loop"}` | label / translation-target ABI helper name                     |
| `string`    | `"a;b"`                  | `{"kind":"string","value":"a;b"}` | **Full only**. Rejected in Core                                |

### 2.1 IR schema v2

- Add `program-ir-v2.schema.json`, representing operands as the tagged objects above.
- **v1 read compatibility**: v1 (operands are raw strings/integers) is normalized to typed operands on load as follows. Integer -> `immediate`; `r` + digits (in range) -> `register`; a name present in the label table -> `symbol`; any other string -> `symbol` (where the instruction allows a symbol) or `string` (where Full allows `string`). Ambiguous cases are **rejected** (no silent guessing).
- v1 output is not maintained. The generator emits v2 for all new output. No compatibility output such as `json --legacy-v1` is provided (v1 is only accepted).
- Like the Core profile stamp, the IR carries a `schema_version`.

### 2.2 String literals (acceptance criteria of #10)

The Full parser satisfies the following.

1. The comment `;` is determined by tracking quote and escape state. `;` and `#` inside quotes are preserved as literals.
2. A quoted operand is always stored as `string`, and is not converted even if its content looks numeric (`"123"`) or like a register (`"r1"`).
3. The empty string `""` can be stored.
4. Escapes are `\"`, `\\`, `\n`, `\t`, `\r`, `\xHH`, `\uHHHH`. Undefined escapes and unclosed quotes are diagnostic errors.
5. The VM distinguishes register references from strings by the operand `kind`. `_value` branches on type and never reinterprets a string as a number/register.

In Core no instruction accepts a `string` operand. This is not a reason to add string-processing instructions to Core (DEC-17).

## 3. Core canonical text grammar (Core v1)

```ebnf
program     = { line } ;
line        = [ label_def | instruction ] , [ comment ] , newline ;
label_def   = ident , ":" ;
instruction = opcode , [ ws , operand , { ws? , "," , ws? , operand } ] ;
comment     = ";" , { any_char_except_newline } ;
opcode      = lower , { lower | digit | "_" } ;
operand     = register | immediate | ident ;
register    = "r" , ( "0" | nonzero_digit [ digit ] ) ;   (* the r0..r31 limit is enforced by validation *)
immediate   = [ "-" ] , ( dec_digits | "0x" , hex_digits ) ;
ident       = ( letter | "_" ) , { letter | digit | "_" } ;
```

Rules:

- A line holds exactly one of an instruction or a label definition. Do not write multiple instructions on one line. A label definition is on its own line (not on the same line as an instruction).
- The opcode is lowercase and case-sensitive. Aliases and PascalCase are rejected in Core.
- A **comma is required** between operands. Whitespace-only separation is rejected. Whitespace after a comma or after the opcode is optional.
- Leading/trailing whitespace, blank lines, and comment-only lines carry no meaning. A tab is the same as whitespace.
- An ident is ASCII only. Duplicate labels and collisions with reserved words (opcode names, `r0`-`r31`) are rejected.
- Out-of-range registers (`r32`), overflow, malformed hexadecimal, a leading `+`, etc. are rejected.
- The operand count and kinds of each instruction are fixed by the registry. The parser validates according to the registry **before execution** (syntax, labels, ranges, profile).
- Line endings are `\n` or `\r\n`. A BOM is rejected. The character encoding is UTF-8. Non-ASCII is allowed only in comments.

Normalized output (canonical emitter):

- One instruction is `opcode<space>op1,<space>op2,<space>op3` (one ASCII space after each comma, one ASCII space after the opcode), indented by 4 spaces outside labels, label lines are `name:`, lines end with `\n`, and the file ends with exactly one newline.
- Immediates are decimal (negative numbers with `-`). `0x` input is normalized to decimal (for ease of comparison).
- `parse(emit(p)) == p` and `emit(parse(canonical)) == canonical` are guaranteed by golden tests.

Example:

```text
entry:
    const r1, 7
    const r2, 1
loop:
    brz r1, done
    sub r1, r1, r2
    jump loop
done:
    halt
```

## 4. Diagnostics (malformed Core)

Diagnostics have a stable code and a position. Message wording may change, but `code` is a compatibility contract.

| code                                                                 | Condition                                                                                 |
| -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `core.syntax.unknown_opcode`                                         | opcode not in the registry / in another profile (including aliases and PascalCase)        |
| `core.syntax.operand_count`                                          | operand count differs from the definition                                                 |
| `core.syntax.operand_kind`                                           | operand kind differs from the definition (e.g. a register where an immediate is required) |
| `core.syntax.separator`                                              | missing or extra comma between operands                                                   |
| `core.syntax.register_range`                                         | outside `r0`-`r31`                                                                        |
| `core.syntax.immediate_range`                                        | immediate outside the range allowed for that instruction                                  |
| `core.syntax.label_dangling` | a label has no instruction after it (IR labels point at instructions) |
| `core.syntax.label_duplicate` / `label_undefined` / `label_reserved` | label rule violation                                                                      |
| `core.syntax.line_form`                                              | multiple instructions on one line, label and instruction on the same line, etc.           |
| `core.syntax.encoding`                                               | UTF-8 violation, BOM, control characters                                                  |
| `core.profile.disallowed`                                            | a Full feature (string operand, etc.) used in Core                                        |

Output: `{"code", "message", "line", "column", "source_line"}`. Multiple diagnostics are returned together, up to N (default 20); processing is not stopped at the first one. The CLI exits non-zero.

## 5. Profile / version contract

- Profile names are `full` and `core`; only `core` has a version, `1` (`2` and later in future). `full` has no version (current compatibility).
- IR stamp: `{"name":"Assam Core","version":"1","registry_schema_version":3}`. The Draft's `"draft"` is **rejected** on load, and a diagnostic points to the migration procedure (after Q4 is settled).
- Compatibility (**syntactic**): the canonical text of a valid Core v`N` program is accepted as-is by the Full text parser as well (the converse of DEC-11 is not required). Therefore the Full registry also lists every Core v`N` instruction via `availability` (adding `const`/`trap`/`hcall`, etc.), and the Full register range is widened to `r0`-`r31` (WP-B1/B3). This is guaranteed by the **Core -> Full upward-compatibility test**.
- **No semantic compatibility is claimed**: Full keeps its current semantics (unbounded integers, sparse memory, etc.), so same-named instructions may produce different results than in Core (e.g. `shl`, `add` overflow). Same-named instructions whose meaning differs are split into per-profile registry entries (separate `id`s). Result comparison is done by per-profile conformance; running a Core program on Full is not guaranteed to give the same result.
- Things that may exist only in Full: PascalCase/aliases, whitespace separation, quoted strings, `Push`/`Pop`, terminal instructions, pseudo-instructions. Pseudo-instructions are allowed only when they can be deterministically lowered to Core, and the result must pass Core validation after translation.
- The Go VM has no grammar of its own and uses the parser/registry of the same version (the shared test inputs are the conformance corpus).

## 6. Acceptance criteria (WP-B1 / WP-B2)

- #10: `Move r0 "a;b"` -> string `a;b`, `"123"` -> string, `"r1"` -> string. Round-trip tests (text -> IR -> JSON -> IR -> text) for the empty string and for strings containing quote/comment symbols.
- #1: parser conformance / golden tests for the grammar above. At least one negative example for every diagnostic code.
- Core -> Full upward-compatibility test; all existing Full tests pass.
- The Go VM accepts/rejects identically given the same registry and corpus (Go is in a separate repository; the corpus is distributed from this repository).
