package core

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"unicode/utf8"
)

var (
	labelRE     = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)
	opcodeRE    = regexp.MustCompile(`^[a-z][a-z0-9]*$`)
	registerRE  = regexp.MustCompile(`^r(0|[1-9]|[12][0-9]|3[01])$`)
	immediateRE = regexp.MustCompile(`^-?(0x[0-9a-fA-F]+|[0-9]+)$`)
)

type instruction struct {
	effect string
	args   []uint64
	line   int
}

// Program is immutable outside this package. Its zero value is not executable.
type Program struct {
	code      []instruction
	canonical string
}

// Canonical returns lowercase comma-separated text, preserving labels and order.
func (p *Program) Canonical() string {
	if p == nil {
		return ""
	}
	return p.canonical
}

type pendingLabel struct {
	instruction, operand, line int
	name                       string
}

// Parse validates the entire program, including unreachable instructions/labels.
func Parse(source, profile string) (*Program, error) {
	if profile != Profile {
		return nil, fmt.Errorf("unsupported profile %q", profile)
	}
	if len(source) > MaxSourceBytes || !utf8.ValidString(source) || strings.ContainsRune(source, 0) {
		return nil, fmt.Errorf("invalid source encoding or source exceeds %d bytes", MaxSourceBytes)
	}
	r, err := loadRegistry()
	if err != nil {
		return nil, err
	}
	p := &Program{}
	labels := map[string]int{}
	var pending []pendingLabel
	var canonical []string
	for index, raw := range strings.Split(source, "\n") {
		line := index + 1
		text := strings.Trim(strings.SplitN(raw, ";", 2)[0], " \t\r")
		if text == "" {
			continue
		}
		fail := func(reason string) (*Program, error) { return nil, fmt.Errorf("line %d: %s", line, reason) }
		if strings.HasSuffix(text, ":") {
			name := strings.TrimSuffix(text, ":")
			if !labelRE.MatchString(name) {
				return fail("invalid standalone label")
			}
			if _, exists := labels[name]; exists {
				return fail("duplicate label")
			}
			labels[name] = len(p.code)
			canonical = append(canonical, name+":")
			continue
		}
		split := strings.IndexAny(text, " \t")
		name, tail := text, ""
		if split >= 0 {
			name, tail = text[:split], strings.Trim(text[split:], " \t")
		}
		d, ok := r.Opcodes[name]
		if !ok {
			return fail("unknown or non-canonical opcode")
		}
		var args []string
		if tail != "" {
			args = strings.Split(tail, ",")
		}
		if len(args) != len(d.Operands) {
			return fail("wrong operand count; use commas")
		}
		ins := instruction{effect: d.Effect, args: make([]uint64, len(args)), line: line}
		for i, kind := range d.Operands {
			a := strings.Trim(args[i], " \t")
			args[i] = a
			switch kind {
			case "write_reg", "read_reg":
				if !registerRE.MatchString(a) {
					return fail("invalid register")
				}
				v, _ := strconv.ParseUint(a[1:], 10, 5)
				ins.args[i] = v
			case "immediate":
				v, err := parseImmediate(a)
				if err != nil {
					return fail(err.Error())
				}
				ins.args[i] = v
				args[i] = strconv.FormatUint(v, 10)
			case "label":
				if !labelRE.MatchString(a) {
					return fail("invalid label operand")
				}
				pending = append(pending, pendingLabel{len(p.code), i, line, a})
			}
		}
		p.code = append(p.code, ins)
		out := name
		if len(args) > 0 {
			out += " " + strings.Join(args, ", ")
		}
		canonical = append(canonical, out)
	}
	if len(p.code) == 0 {
		return nil, fmt.Errorf("program contains no instructions")
	}
	for name, target := range labels {
		if target >= len(p.code) {
			return nil, fmt.Errorf("label %q targets end of program", name)
		}
	}
	for _, ref := range pending {
		target, exists := labels[ref.name]
		if !exists {
			return nil, fmt.Errorf("line %d: unresolved label %q", ref.line, ref.name)
		}
		p.code[ref.instruction].args[ref.operand] = uint64(target)
	}
	p.canonical = strings.Join(canonical, "\n") + "\n"
	if len(p.canonical) > MaxSourceBytes {
		return nil, fmt.Errorf("canonical source exceeds %d bytes", MaxSourceBytes)
	}
	return p, nil
}

func parseImmediate(s string) (uint64, error) {
	if !immediateRE.MatchString(s) {
		return 0, fmt.Errorf("invalid integer immediate")
	}
	negative := strings.HasPrefix(s, "-")
	digits := strings.TrimPrefix(s, "-")
	base := 10
	if strings.HasPrefix(digits, "0x") {
		base, digits = 16, digits[2:]
	}
	v, err := strconv.ParseUint(digits, base, 64)
	if err != nil || (negative && v > uint64(1)<<63) {
		return 0, fmt.Errorf("integer immediate out of range")
	}
	if negative {
		v = -v
	}
	return v, nil
}
