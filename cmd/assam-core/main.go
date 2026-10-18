// assam-core is the experimental Go bootstrap runner, not the legacy Full CLI.
package main

import (
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"

	"github.com/tomiya7688/Assam/core"
)

func main() { os.Exit(run()) }
func run() int {
	profile := flag.String("profile", "", "required: "+core.Profile+" or "+core.MemoryProfile)
	budget := flag.Uint64("max-steps", 10000, "maximum attempted instructions")
	emit := flag.Bool("canonical", false, "validate and emit canonical text")
	memoryBytes := flag.Uint64("memory-bytes", 0, "draft.2 memory size, max 16777216")
	memoryHex := flag.String("memory-hex", "", "draft.2 initial bytes as hex; remainder is zero")
	dumpMemory := flag.Bool("dump-memory", false, "include final memory_hex in execution JSON")
	flag.Parse()
	memoryFlags := false
	flag.Visit(func(f *flag.Flag) {
		if f.Name == "memory-bytes" || f.Name == "memory-hex" || f.Name == "dump-memory" {
			memoryFlags = true
		}
	})
	if memoryFlags && (*profile != core.MemoryProfile || *emit) {
		fmt.Fprintln(os.Stderr, "memory flags require draft.2 execution (not -canonical)")
		return 2
	}
	if *memoryBytes > core.MaxMemoryBytes || uint64(len(*memoryHex)) > 2*(*memoryBytes) || len(*memoryHex)%2 != 0 {
		fmt.Fprintln(os.Stderr, "invalid memory size/image (maximum 16777216 bytes)")
		return 2
	}
	if flag.NArg() != 1 {
		fmt.Fprintln(os.Stderr, "usage: assam-core -profile PROFILE [-max-steps N] [-canonical] [-memory-bytes N] [-memory-hex HEX] [-dump-memory] FILE|-")
		return 2
	}
	input := os.Stdin
	if flag.Arg(0) != "-" {
		var err error
		input, err = os.Open(flag.Arg(0))
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 2
		}
		defer input.Close()
	}
	data, err := io.ReadAll(io.LimitReader(input, core.MaxSourceBytes+1))
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	program, err := core.Parse(string(data), *profile)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	if *emit {
		if _, err := fmt.Fprint(os.Stdout, program.Canonical()); err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 2
		}
		return 0
	}
	var result core.Result
	var finalMemory *string
	if *profile == core.MemoryProfile {
		initial := make([]byte, int(*memoryBytes)) // cap checked before conversion/allocation
		if _, err := hex.Decode(initial, []byte(*memoryHex)); err != nil {
			fmt.Fprintln(os.Stderr, "invalid memory hex:", err)
			return 2
		}
		execution, err := core.RunWithMemory(program, *budget, initial)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 2
		}
		result = execution.Result
		if *dumpMemory {
			text := hex.EncodeToString(execution.Memory)
			finalMemory = &text
		}
	} else {
		result = core.Run(program, *budget)
	}
	output := struct {
		core.Result
		MemoryHex *string `json:"memory_hex,omitempty"`
	}{result, finalMemory}
	if err := json.NewEncoder(os.Stdout).Encode(output); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	if result.Status != "halted" {
		return 1
	}
	return 0
}
