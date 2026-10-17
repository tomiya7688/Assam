// assam-core is the experimental Go bootstrap runner, not the legacy Full CLI.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"

	"github.com/tomiya7688/Assam/core"
)

func main() { os.Exit(run()) }
func run() int {
	profile := flag.String("profile", "", "required: "+core.Profile)
	budget := flag.Uint64("max-steps", 10000, "maximum attempted instructions")
	emit := flag.Bool("canonical", false, "validate and emit canonical text")
	flag.Parse()
	if flag.NArg() != 1 {
		fmt.Fprintln(os.Stderr, "usage: assam-core -profile "+core.Profile+" [-max-steps N] [-canonical] FILE|-")
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
	result := core.Run(program, *budget)
	if err := json.NewEncoder(os.Stdout).Encode(result); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	if result.Status != "halted" {
		return 1
	}
	return 0
}
