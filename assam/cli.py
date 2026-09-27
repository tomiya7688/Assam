import argparse
from pathlib import Path
from .generator import read
from .parser import parse_program
from .vm import VM
def main(argv=None):
    parser=argparse.ArgumentParser(prog="assam"); sub=parser.add_subparsers(dest="command",required=True)
    run=sub.add_parser("run"); run.add_argument("file",type=Path); run.add_argument("--json",action="store_true")
    convert=sub.add_parser("json"); convert.add_argument("source",type=Path); convert.add_argument("-o","--output",type=Path)
    args=parser.parse_args(argv)
    if args.command=="run":
        p=read(args.file) if args.json else parse_program(args.file.read_text(encoding="utf-8")); print(VM(p).run())
    else:
        output=parse_program(args.source.read_text(encoding="utf-8")).to_json()
        if args.output: args.output.write_text(output+"\n",encoding="utf-8")
        else: print(output)
    return 0
if __name__=="__main__": raise SystemExit(main())