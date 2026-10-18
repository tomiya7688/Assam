package core

import (
	"bytes"
	_ "embed"
	"encoding/json"
	"fmt"
	"io"
	"slices"
)

// MemoryProfile adds memory without changing the previously published draft.1.
const MemoryProfile = "assam-core/v1-draft.2"

//go:embed registry-memory.json
var memoryRegistryJSON []byte

type memoryDefinition struct {
	Bytes  uint64 `json:"bytes"`
	Signed bool   `json:"signed"`
}

type memoryContract struct {
	AddressBits int    `json:"address_bits"`
	ByteOrder   string `json:"byte_order"`
	Unaligned   bool   `json:"unaligned"`
	BoundsTrap  string `json:"bounds_trap"`
}

type memoryExtension struct {
	Profile string                `json:"profile"`
	Extends string                `json:"extends"`
	Status  string                `json:"status"`
	Memory  memoryContract        `json:"memory"`
	Opcodes map[string]definition `json:"opcodes"`
}

// SchemaForProfile returns a resolved, independent JSON registry. The memory
// extension inherits the original opcode table rather than copying it. Schema()
// continues to return the exact original draft.1 bytes for existing consumers.
func SchemaForProfile(profile string) ([]byte, error) {
	r, err := registryForProfile(profile)
	if err != nil {
		return nil, err
	}
	return json.MarshalIndent(r, "", "  ")
}

func registryForProfile(profile string) (registry, error) {
	if profile != Profile && profile != MemoryProfile {
		return registry{}, fmt.Errorf("unsupported profile %q", profile)
	}
	r, err := loadRegistry()
	if err != nil || profile == Profile {
		return r, err
	}
	return extendMemoryRegistry(r, memoryRegistryJSON)
}

func extendMemoryRegistry(r registry, data []byte) (registry, error) {
	var ext memoryExtension
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&ext); err != nil {
		return r, fmt.Errorf("memory registry: %w", err)
	}
	if dec.Decode(new(any)) != io.EOF {
		return r, fmt.Errorf("memory registry: trailing data")
	}
	if ext.Profile != MemoryProfile || ext.Extends != Profile ||
		ext.Status != "experimental-subset" || len(ext.Opcodes) == 0 ||
		ext.Memory != (memoryContract{64, "little", true, "memory_out_of_bounds"}) {
		return r, fmt.Errorf("memory registry: unsupported contract")
	}
	// Validate the complete extension before modifying even the local registry.
	for name, d := range ext.Opcodes {
		_, conflict := r.Opcodes[name]
		if conflict || !opcodeRE.MatchString(name) || d.Memory == nil ||
			!slices.Equal(d.Traps, []string{"memory_out_of_bounds"}) {
			return r, fmt.Errorf("memory registry: invalid opcode %q", name)
		}
		m := d.Memory
		if m.Bytes != 1 && m.Bytes != 2 && m.Bytes != 4 && m.Bytes != 8 {
			return r, fmt.Errorf("memory registry: invalid width for %q", name)
		}
		switch d.Effect {
		case "load":
			if !slices.Equal(d.Operands, []string{"write_reg", "read_reg"}) {
				return r, fmt.Errorf("memory registry: invalid load operands")
			}
		case "store":
			if m.Signed || !slices.Equal(d.Operands, []string{"read_reg", "read_reg"}) {
				return r, fmt.Errorf("memory registry: invalid store operands")
			}
		default:
			return r, fmt.Errorf("memory registry: unsupported effect %q", d.Effect)
		}
	}
	for name, d := range ext.Opcodes {
		r.Opcodes[name] = d
	}
	r.Profile, r.Memory = MemoryProfile, &ext.Memory
	return r, nil
}
