// Package core implements an experimental arithmetic/control-flow Core subset.
// It is not a stable Core v1 implementation; see doc/core-bootstrap.md.
package core

import (
	"bytes"
	_ "embed"
	"encoding/json"
	"fmt"
	"io"
)

//go:embed registry.json
var registryJSON []byte

// Profile must be selected explicitly; legacy Full ASSAM is never auto-detected.
const Profile = "assam-core/v1-draft.1"
const MaxSourceBytes = 1 << 20

type definition struct {
	Operands []string `json:"operands"`
	Effect   string   `json:"effect"`
	Traps    []string `json:"traps"`
}
type registry struct {
	Profile       string                `json:"profile"`
	Status        string                `json:"status"`
	RegisterCount int                   `json:"register_count"`
	RegisterBits  int                   `json:"register_bits"`
	Targets       []string              `json:"required_translation_targets"`
	Opcodes       map[string]definition `json:"opcodes"`
}

// Schema returns a copy so callers cannot mutate the embedded contract.
func Schema() []byte { return append([]byte(nil), registryJSON...) }

func loadRegistry() (registry, error) {
	var r registry
	dec := json.NewDecoder(bytes.NewReader(registryJSON))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&r); err != nil {
		return r, fmt.Errorf("registry: %w", err)
	}
	if dec.Decode(new(any)) != io.EOF {
		return r, fmt.Errorf("registry: trailing data")
	}
	if r.Profile != Profile || r.Status != "experimental-subset" || r.RegisterCount != 32 || r.RegisterBits != 64 || len(r.Opcodes) == 0 {
		return r, fmt.Errorf("registry: unsupported contract")
	}
	for name, d := range r.Opcodes {
		if !opcodeRE.MatchString(name) || d.Operands == nil || d.Traps == nil {
			return r, fmt.Errorf("registry: malformed opcode %q", name)
		}
		for _, k := range d.Operands {
			switch k {
			case "write_reg", "read_reg", "immediate", "label":
			default:
				return r, fmt.Errorf("registry: unknown operand kind %q", k)
			}
		}
	}
	return r, nil
}
