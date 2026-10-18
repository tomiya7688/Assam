package core

import (
	"bytes"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math/bits"
	"os"
	"reflect"
	"strings"
	"sync"
	"testing"
)

type memoryFixture struct {
	fixture
	Initial string `json:"initial_memory_hex"`
	Final   string `json:"expected_memory_hex"`
}

func TestMemoryCorpus(t *testing.T) {
	data, err := os.ReadFile("../testdata/core-memory.json")
	if err != nil {
		t.Fatal(err)
	}
	var corpus struct {
		Profile string
		Valid   []memoryFixture
		Invalid []string
	}
	if err := json.Unmarshal(data, &corpus); err != nil {
		t.Fatal(err)
	}
	if corpus.Profile != MemoryProfile {
		t.Fatal("memory profile drift")
	}
	covered := map[string]bool{}
	for _, c := range corpus.Valid {
		t.Run(c.Name, func(t *testing.T) {
			p, err := Parse(c.Source, MemoryProfile)
			if err != nil {
				t.Fatal(err)
			}
			initial, err := hex.DecodeString(c.Initial)
			if err != nil {
				t.Fatal(err)
			}
			before := append([]byte(nil), initial...)
			result, err := RunWithMemory(p, c.Budget, initial)
			if err != nil {
				t.Fatal(err)
			}
			got, want := result.Result, c.Expected
			if got.Status != want.Status || got.Code != want.Code ||
				want.PC == nil || got.PC != *want.PC ||
				want.Steps == nil || got.Steps != *want.Steps ||
				want.Line == nil || got.Line != *want.Line {
				t.Fatalf("got %+v, want %+v", got, want)
			}
			for register, value := range want.Registers {
				var index int
				if _, err := fmt.Sscan(register, &index); err != nil || index < 0 || index > 31 {
					t.Fatal("invalid fixture register")
				}
				if got.Registers[index] != value {
					t.Fatalf("r%d=%s, want %s", index, got.Registers[index], value)
				}
			}
			if hex.EncodeToString(result.Memory) != c.Final {
				t.Fatalf("memory %x, want %s", result.Memory, c.Final)
			}
			if !bytes.Equal(before, initial) {
				t.Fatal("mutated caller memory")
			}
			again, err := RunWithMemory(p, c.Budget, initial)
			if err != nil || !reflect.DeepEqual(result, again) {
				t.Fatal("non-deterministic replay")
			}
			q, err := Parse(p.Canonical(), MemoryProfile)
			if err != nil || q.Canonical() != p.Canonical() {
				t.Fatal("canonical roundtrip")
			}
			normalized, err := RunWithMemory(q, c.Budget, initial)
			result.Result.Line, normalized.Result.Line = 0, 0
			if err != nil || !reflect.DeepEqual(result, normalized) {
				t.Fatal("canonical execution changed")
			}
			for _, line := range strings.Split(p.Canonical(), "\n") {
				if fields := strings.Fields(line); len(fields) > 0 {
					covered[fields[0]] = true
				}
			}
		})
	}
	var ext memoryExtension
	if err := json.Unmarshal(memoryRegistryJSON, &ext); err != nil {
		t.Fatal(err)
	}
	for name := range ext.Opcodes {
		if !covered[name] {
			t.Errorf("missing golden fixture for %s", name)
		}
		if _, err := Parse(name+" r1, r0\nhalt", Profile); err == nil {
			t.Errorf("draft.1 accepted %s", name)
		}
	}
	for _, source := range corpus.Invalid {
		if _, err := Parse(source, MemoryProfile); err == nil {
			t.Errorf("accepted malformed memory source %q", source)
		}
	}
}

func TestMemoryConfigurationAndOwnership(t *testing.T) {
	p, err := Parse("const r1, 7\nstore8 r0, r1\nhalt", MemoryProfile)
	if err != nil {
		t.Fatal(err)
	}
	legacy, _ := Parse("halt", Profile)
	for _, invalid := range []*Program{nil, {}, legacy} {
		if _, err := RunWithMemory(invalid, 1, nil); err == nil {
			t.Fatal("accepted invalid program/profile")
		}
	}
	if _, err := RunWithMemory(p, 3, make([]byte, MaxMemoryBytes+1)); err == nil {
		t.Fatal("missing resource cap")
	}
	halt, _ := Parse("halt", MemoryProfile)
	if result, err := RunWithMemory(halt, 1, make([]byte, MaxMemoryBytes)); err != nil || len(result.Memory) != MaxMemoryBytes {
		t.Fatal("rejected maximum memory size")
	}
	initial := []byte{42}
	first, err := RunWithMemory(p, 3, initial)
	if err != nil {
		t.Fatal(err)
	}
	first.Memory[0] = 99
	second, err := RunWithMemory(p, 3, initial)
	if err != nil || initial[0] != 42 || second.Memory[0] != 7 {
		t.Fatal("shared mutable memory")
	}
	if result := Run(p, 3); result.Code != "memory_out_of_bounds" {
		t.Fatal("Run should have zero bytes of guest memory")
	}
	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			result, err := RunWithMemory(p, 3, initial)
			if err != nil || result.Memory[0] != 7 {
				t.Error("concurrent independent run")
			}
		}()
	}
	wg.Wait()
}

func TestMemoryProfilePreservesArithmetic(t *testing.T) {
	valid, _ := corpus(t)
	for _, c := range valid {
		old, err := Parse(c.Source, Profile)
		if err != nil {
			t.Fatal(err)
		}
		p, err := Parse(c.Source, MemoryProfile)
		if err != nil {
			t.Fatal(err)
		}
		got, err := RunWithMemory(p, c.Budget, nil)
		if err != nil || !reflect.DeepEqual(Run(old, c.Budget), got.Result) {
			t.Fatalf("arithmetic drift: %s", c.Name)
		}
	}
}

func TestMemoryRangeAndSchema(t *testing.T) {
	for _, c := range []struct {
		size, address, width uint64
		valid                bool
	}{
		{8, 0, 8, true}, {9, 1, 8, true}, {8, 1, 8, false},
		{0, 0, 1, false}, {8, 0, 0, false}, {8, ^uint64(0), 8, false},
		{8, 1 << 32, 1, false}, {8, ^uint64(0) - 7, 8, false},
	} {
		if memoryRangeValid(c.size, c.address, c.width) != c.valid {
			t.Fatalf("bounds case %+v", c)
		}
	}
	for _, profile := range []string{Profile, MemoryProfile} {
		data, err := SchemaForProfile(profile)
		if err != nil {
			t.Fatal(err)
		}
		var registry registry
		if err := json.Unmarshal(data, &registry); err != nil || registry.Profile != profile {
			t.Fatal("resolved schema")
		}
		data[0] = '!'
		if _, err := SchemaForProfile(profile); err != nil {
			t.Fatal("mutable schema")
		}
	}
	if _, err := SchemaForProfile("assam-core/v1"); err == nil {
		t.Fatal("stable profile not implemented")
	}
	for _, mutate := range []func(*memoryExtension){
		func(e *memoryExtension) { e.Extends = "wrong" },
		func(e *memoryExtension) { e.Status = "stable" },
		func(e *memoryExtension) { e.Memory.AddressBits = 32 },
		func(e *memoryExtension) { e.Memory.ByteOrder = "big" },
		func(e *memoryExtension) { e.Opcodes["const"] = e.Opcodes["load8u"] },
		func(e *memoryExtension) { d := e.Opcodes["load8u"]; d.Memory = nil; e.Opcodes["load8u"] = d },
		func(e *memoryExtension) { e.Opcodes["load8u"].Memory.Bytes = 3 },
		func(e *memoryExtension) { d := e.Opcodes["load8u"]; d.Effect = "other"; e.Opcodes["load8u"] = d },
		func(e *memoryExtension) { e.Opcodes["store8"].Memory.Signed = true },
		func(e *memoryExtension) {
			d := e.Opcodes["load8u"]
			d.Operands = []string{"read_reg"}
			e.Opcodes["load8u"] = d
		},
		func(e *memoryExtension) { d := e.Opcodes["store8"]; d.Traps = nil; e.Opcodes["store8"] = d },
	} {
		var ext memoryExtension
		if err := json.Unmarshal(memoryRegistryJSON, &ext); err != nil {
			t.Fatal(err)
		}
		mutate(&ext)
		data, err := json.Marshal(ext)
		if err != nil {
			t.Fatal(err)
		}
		base, err := loadRegistry()
		if err != nil {
			t.Fatal(err)
		}
		if _, err := extendMemoryRegistry(base, data); err == nil {
			t.Fatal("accepted invalid memory schema")
		}
		if len(base.Opcodes) != 22 {
			t.Fatal("failed extension partially mutated base")
		}
	}
	for _, data := range [][]byte{[]byte("{}"), append(append([]byte(nil), memoryRegistryJSON...), []byte(" {}")...), bytes.Replace(memoryRegistryJSON, []byte(`"extends"`), []byte(`"unknown"`), 1)} {
		base, _ := loadRegistry()
		if _, err := extendMemoryRegistry(base, data); err == nil {
			t.Fatal("accepted malformed registry")
		}
	}
}

func FuzzMemoryAccess(f *testing.F) {
	for _, address := range []uint64{0, 1, 7, 8, 1 << 32, ^uint64(0)} {
		f.Add(address, uint64(0x8123456789abcdef), uint8(8), uint8(3))
	}
	f.Fuzz(func(t *testing.T, address, value uint64, size, selector uint8) {
		width := uint64(1) << (selector % 4)
		load := fmt.Sprintf("load%du", width*8)
		if width == 8 {
			load = "load64"
		}
		source := fmt.Sprintf("const r1, %d\nconst r2, %d\nstore%d r1, r2\n%s r3, r1\nhalt", address, value, width*8, load)
		p, err := Parse(source, MemoryProfile)
		if err != nil {
			t.Fatal(err)
		}
		initial := bytes.Repeat([]byte{0xaa}, int(size))
		got, err := RunWithMemory(p, 5, initial)
		if err != nil {
			t.Fatal(err)
		}
		// Carry-aware addition is independent of the executor's subtraction check.
		end, carry := bits.Add64(address, width, 0)
		valid := carry == 0 && end <= uint64(size)
		if !valid {
			if got.Result.Code != "memory_out_of_bounds" || !bytes.Equal(got.Memory, initial) {
				t.Fatal("invalid access mutated state")
			}
		} else {
			want := value
			if width < 8 {
				want &= (uint64(1) << (8 * width)) - 1
			}
			if got.Result.Status != "halted" || got.Result.Registers[3] != fmt.Sprintf("0x%016x", want) {
				t.Fatal("load/store roundtrip")
			}
			for i, b := range initial {
				if b != 0xaa {
					t.Fatalf("changed caller byte %d", i)
				}
			}
			for i, b := range got.Memory {
				if uint64(i) < address || uint64(i) >= address+width {
					if b != 0xaa {
						t.Fatal("write outside selected region")
					}
				}
			}
		}
	})
}
