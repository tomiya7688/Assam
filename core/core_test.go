package core

import (
	"encoding/json"
	"os"
	"reflect"
	"strconv"
	"strings"
	"testing"
)

type fixture struct {
	Name     string `json:"name"`
	Source   string `json:"source"`
	Budget   uint64 `json:"budget"`
	Expected struct {
		Status    string            `json:"status"`
		Code      string            `json:"code"`
		PC        *int              `json:"pc"`
		Steps     *uint64           `json:"steps"`
		Line      *int              `json:"line"`
		Registers map[string]string `json:"registers"`
	} `json:"expected"`
}

func corpus(t *testing.T) ([]fixture, []string) {
	t.Helper()
	data, err := os.ReadFile("../testdata/core-v1.json")
	if err != nil {
		t.Fatal(err)
	}
	var c struct {
		Profile string
		Valid   []fixture
		Invalid []string
	}
	if err := json.Unmarshal(data, &c); err != nil {
		t.Fatal(err)
	}
	if c.Profile != Profile {
		t.Fatal("corpus profile drift")
	}
	return c.Valid, c.Invalid
}
func TestConformance(t *testing.T) {
	valid, invalid := corpus(t)
	for _, c := range valid {
		t.Run(c.Name, func(t *testing.T) {
			p, err := Parse(c.Source, Profile)
			if err != nil {
				t.Fatal(err)
			}
			result := Run(p, c.Budget)
			e := c.Expected
			if result.Status != e.Status || result.Code != e.Code ||
				(e.PC != nil && result.PC != *e.PC) ||
				(e.Steps != nil && result.Steps != *e.Steps) ||
				(e.Line != nil && result.Line != *e.Line) {
				t.Fatalf("result: %+v; expected %+v", result, e)
			}
			for key, value := range e.Registers {
				i, err := strconv.Atoi(key)
				if err != nil || i < 0 || i >= 32 {
					t.Fatal("invalid fixture register")
				}
				if result.Registers[i] != value {
					t.Fatalf("r%d = %s, want %s", i, result.Registers[i], value)
				}
			}
			if !reflect.DeepEqual(result, Run(p, c.Budget)) {
				t.Fatal("non-deterministic replay")
			}
			roundtrip, err := Parse(p.Canonical(), Profile)
			if err != nil || roundtrip.Canonical() != p.Canonical() {
				t.Fatalf("unstable canonical text: %v", err)
			}
			result2 := Run(roundtrip, c.Budget)
			// Source locations change when comments/blank lines are normalized.
			result.Line, result2.Line = 0, 0
			if !reflect.DeepEqual(result, result2) {
				t.Fatal("canonical roundtrip changed execution")
			}
		})
	}
	for i, source := range invalid {
		t.Run("invalid_"+strconv.Itoa(i), func(t *testing.T) {
			if _, err := Parse(source, Profile); err == nil {
				t.Fatalf("accepted invalid source: %q", source)
			}
		})
	}
}
func TestBoundaries(t *testing.T) {
	for _, profile := range []string{"", "full", "assam-core/v1", "assam-core/v2"} {
		if _, err := Parse("halt", profile); err == nil {
			t.Fatalf("accepted profile %q", profile)
		}
	}
	if _, err := Parse(strings.Repeat(" ", MaxSourceBytes+1), Profile); err == nil {
		t.Fatal("source limit")
	}
	if _, err := Parse(string([]byte{0xff}), Profile); err == nil {
		t.Fatal("invalid UTF-8")
	}
	if Run(nil, 1).Status != "invalid_program" || Run(&Program{}, 1).Status != "invalid_program" {
		t.Fatal("zero-value program")
	}
	data := Schema()
	data[0] = '!'
	if _, err := loadRegistry(); err != nil {
		t.Fatal("caller mutated schema")
	}
	p, err := Parse("const r1, "+strings.Repeat("0", 5000)+"1\nhalt", Profile)
	if err != nil || Run(p, 2).Registers[1] != "0x0000000000000001" {
		t.Fatal("leading zero decimal")
	}
}
func FuzzParse(f *testing.F) {
	for _, seed := range []string{"halt", "const r1, 1\nhalt", "loop:\njump loop", "const r32, 1", "const r1 2"} {
		f.Add(seed)
	}
	f.Fuzz(func(t *testing.T, source string) {
		p, err := Parse(source, Profile)
		if err != nil {
			return
		}
		result := Run(p, 16)
		if result.Status == "internal_error" {
			t.Fatalf("accepted unimplemented effect: %+v", result)
		}
		if result.Registers[0] != "0x0000000000000000" {
			t.Fatal("r0 changed")
		}
		q, err := Parse(p.Canonical(), Profile)
		if err != nil || q.Canonical() != p.Canonical() {
			t.Fatal("canonical parse failed")
		}
	})
}
