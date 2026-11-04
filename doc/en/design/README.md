# ASSAM Design Documents

Language: [日本語](../../jp/設計/README.md) | English

The canonical design derived from GitHub Issues #1-#6, #10, #13-#15, #28, #29. The Japanese version is canonical; the English version is synchronized in the same change. Implementers read **only the sections needed for their own work package (WP)**.

## Reading order

1. [Implementation plan](implementation-plan.md) - the row for your WP and its "design references"
2. [Decision log](decision-log.md) - confirmed, proposed, and open decisions. Check for blockers
3. Only the sections named by the design references

## Document list

| Document                                                         | Contents                                                                       | Issue       |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------ | ----------- |
| [Overall design](overview.md)                                    | Purpose, principles, profile system, current-vs-target gaps, phases, non-goals | All         |
| [Core grammar and profile contract](core-grammar-and-profile.md) | Typed operands, canonical grammar, diagnostics, profile/version                | #1, #10     |
| [Core semantics](core-semantics.md)                              | Machine model, instruction list, traps, Bitlang Low lowering, hcall            | #3          |
| [Registry and conformance](registry-and-conformance.md)          | registry v3, conformance corpus, CI gates                                      | #2, #8, #13 |
| [Target translation](target-translation.md)                      | Mapping table v2, admission gate, verification tiers, Wasm/JVM, custom targets | #4, #5, #6  |
| [Additional runtimes](additional-runtimes.md)                    | Java VM, Rust VM                                                               | #14, #15    |
| [Distribution and supply chain](supply-chain.md)                 | Artifact signing and attestation, Python certificate handling                  | #28, #29    |
| [Implementation plan](implementation-plan.md)                    | Work packages, dependencies, acceptance criteria, operating rules              | All         |
| [Decision log](decision-log.md)                                  | List of design decisions                                                       | All         |

## Relationship between design and implementation

- The design describes the **target state**. Differences from the current implementation are in the gap table in [Overall design section 4](overview.md). Until the implementation catches up, the design documents do not necessarily hold for the current code. For current code behavior, see the [instruction set specification](../instruction-set.md) and [Assam Core](../assam-core.md) (Draft).
- If the design is insufficient or contradictory, fix it in a design PR before implementing ([Implementation plan section 4](implementation-plan.md)).
