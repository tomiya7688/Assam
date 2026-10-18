package core

import "fmt"

// MaxMemoryBytes is a bootstrap host resource cap, not the architectural address
// width. Every access still uses unsigned 64-bit guest addresses on all hosts.
const MaxMemoryBytes = 16 << 20

// MemoryExecution owns its final memory snapshot. It never aliases the caller's
// initial image or another execution. Result retains the original JSON contract.
type MemoryExecution struct {
	Result Result
	Memory []byte
}

// RunWithMemory runs a fresh draft.2 machine using a copy of initial memory.
// The caller must not mutate initial concurrently while this call copies it.
// Configuration errors are returned before execution; guest faults are Results.
// The zero-length image is valid, but every load/store on it traps.
func RunWithMemory(p *Program, budget uint64, initial []byte) (MemoryExecution, error) {
	if p == nil || len(p.code) == 0 || p.profile != MemoryProfile {
		return MemoryExecution{}, fmt.Errorf("memory execution requires a validated %s program", MemoryProfile)
	}
	if len(initial) > MaxMemoryBytes {
		return MemoryExecution{}, fmt.Errorf("initial memory exceeds %d bytes", MaxMemoryBytes)
	}
	memory := append([]byte(nil), initial...)
	return MemoryExecution{Result: run(p, budget, memory), Memory: memory}, nil
}

// Use subtraction after validating size, never address+width: that sum can wrap
// before a bounds check. The caller only converts a validated address to int.
func memoryRangeValid(size, address, width uint64) bool {
	return width != 0 && width <= size && address <= size-width
}
