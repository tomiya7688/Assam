package core

import "fmt"

// Result reports a deterministic snapshot. Registers are hex strings to avoid
// lossy JSON numeric conversions in JavaScript and future cross-language tools.
type Result struct {
	Status    string     `json:"status"`
	PC        int        `json:"pc"`
	Steps     uint64     `json:"steps"`
	Line      int        `json:"line"`
	Code      string     `json:"code"`
	Registers [32]string `json:"registers"`
}

// Run starts a fresh machine. A budget is mandatory and counts attempted
// instructions, including halt/trap. Reaching halt on the final step succeeds.
func Run(p *Program, budget uint64) Result {
	var regs [32]uint64
	pc := 0
	var steps uint64
	snapshot := func(status, code string, line int) Result {
		r := Result{Status: status, PC: pc, Steps: steps, Line: line, Code: code}
		for i, v := range regs {
			r.Registers[i] = fmt.Sprintf("0x%016x", v)
		}
		return r
	}
	if p == nil || len(p.code) == 0 {
		return snapshot("invalid_program", "", 0)
	}
	for {
		if steps >= budget {
			return snapshot("step_limit", "", 0)
		}
		if pc < 0 || pc >= len(p.code) {
			return snapshot("trap", "invalid_pc", 0)
		}
		ins := p.code[pc]
		a := ins.args
		steps++
		next := pc + 1
		var value uint64
		write := false
		switch ins.effect {
		case "constant":
			value, write = a[1], true
		case "branch_zero", "branch_nonzero":
			take := regs[a[0]] == 0
			if ins.effect == "branch_nonzero" {
				take = !take
			}
			if take {
				next = int(a[1])
			}
		case "jump":
			next = int(a[0])
		case "halt":
			return snapshot("halted", "", ins.line)
		case "trap":
			return snapshot("trap", fmt.Sprintf("explicit:0x%016x", a[0]), ins.line)
		default:
			// The registry defines operand spelling/order; this switch only
			// implements semantic effects. Never evaluate unselected division.
			if len(a) != 3 {
				return snapshot("internal_error", "unsupported_effect", ins.line)
			}
			x, y := regs[a[1]], regs[a[2]]
			write = true
			switch ins.effect {
			case "add":
				value = x + y
			case "sub":
				value = x - y
			case "mul":
				value = x * y
			case "and":
				value = x & y
			case "or":
				value = x | y
			case "xor":
				value = x ^ y
			case "shl":
				value = x << (y & 63)
			case "shr":
				value = x >> (y & 63)
			case "sar":
				value = uint64(int64(x) >> (y & 63))
			case "eq":
				if x == y {
					value = 1
				}
			case "ltu":
				if x < y {
					value = 1
				}
			case "lts":
				if int64(x) < int64(y) {
					value = 1
				}
			case "divu", "divs", "remu", "rems":
				if y == 0 {
					return snapshot("trap", "division_by_zero", ins.line)
				}
				switch ins.effect {
				case "divu":
					value = x / y
				case "remu":
					value = x % y
				case "divs":
					value = uint64(int64(x) / int64(y))
				case "rems":
					value = uint64(int64(x) % int64(y))
				}
			default:
				return snapshot("internal_error", "unsupported_effect", ins.line)
			}
		}
		if write && a[0] != 0 {
			regs[a[0]] = value
		}
		pc = next
	}
}
