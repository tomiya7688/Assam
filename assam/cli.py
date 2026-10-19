import argparse
import json
import sys
from pathlib import Path
from .generator import read
from .parser import parse_program
from .vm import VM
from .c_frontend import CTranslator
from .analyzer import ProgramAnalyzer
from .instruction_set import InstructionSet
from .target_coverage import build_target_coverage_template, check_target_coverage, check_target_mappings, check_target_matrix
def main(argv=None):
    parser=argparse.ArgumentParser(prog="assam"); sub=parser.add_subparsers(dest="command",required=True)
    run=sub.add_parser("run"); run.add_argument("file",type=Path); run.add_argument("--json",action="store_true"); run.add_argument("--profile",choices=("core","full"))
    convert=sub.add_parser("json"); convert.add_argument("source",type=Path); convert.add_argument("-o","--output",type=Path); convert.add_argument("--profile",choices=("core",),help="validate and mark the output as Assam Core")
    c_convert=sub.add_parser("from-c",help="translate the supported C integer subset to ASSAM")
    c_convert.add_argument("source",type=Path); c_convert.add_argument("-o","--output",type=Path)
    analyze=sub.add_parser("analyze",help="show static instruction and control-flow analysis")
    analyze.add_argument("file",type=Path); analyze.add_argument("--ir-json",action="store_true"); analyze.add_argument("--profile",choices=("core","full"))
    analyze.add_argument("--format",choices=("text","json"),default="text")
    coverage=sub.add_parser("check-target-coverage",help="check a target coverage manifest against the Core registry")
    coverage.add_argument("manifest",type=Path); coverage.add_argument("--registry",type=Path,help="instruction registry JSON (defaults to the bundled registry)")
    coverage.add_argument("--format",choices=("text","json"),default="text",help="report format")
    mappings=sub.add_parser("check-target-mappings",help="check target mapping structure and Core hook references")
    mappings.add_argument("mapping",type=Path); mappings.add_argument("--registry",type=Path,help="instruction registry JSON (defaults to the bundled registry)")
    mappings.add_argument("--coverage",type=Path,help="require mappings to match this target's in_scope coverage declarations")
    mappings.add_argument("--format",choices=("text","json"),default="text",help="report format")
    matrix=sub.add_parser("check-target-matrix",help="check Core coverage declarations for x64, ARM64, and RISC-V")
    matrix.add_argument("manifests",type=Path,nargs="+"); matrix.add_argument("--registry",type=Path,help="instruction registry JSON (defaults to the bundled registry)")
    matrix.add_argument("--format",choices=("text","json"),default="text",help="report format")
    scaffold=sub.add_parser("scaffold-target-coverage",help="print a review-required coverage manifest for one target")
    scaffold.add_argument("architecture"); scaffold.add_argument("profile"); scaffold.add_argument("--registry",type=Path,help="instruction registry JSON (defaults to the bundled registry)")
    args=parser.parse_args(argv)
    try:
        if args.command=="run":
            p=read(args.file) if args.json else parse_program(args.file.read_text(encoding="utf-8")); print(VM(p,profile=args.profile).run())
        elif args.command=="json":
            program=parse_program(args.source.read_text(encoding="utf-8"))
            if args.profile == "core":
                instruction_set=InstructionSet()
                instruction_set.validate(program,profile="core")
                program.profile=instruction_set.core_profile_marker()
            output=program.to_json()
            if args.output: args.output.write_text(output+"\n",encoding="utf-8")
            else: print(output)
        elif args.command=="from-c":
            translator=CTranslator()
            output=translator.to_source(translator.translate(args.source.read_text(encoding="utf-8")))
            if args.output: args.output.write_text(output,encoding="utf-8")
            else: print(output,end="")
        elif args.command=="check-target-coverage":
            report=check_target_coverage(args.manifest,args.registry)
            if args.format=="json": print(json.dumps(report,ensure_ascii=False,indent=2))
            else: print(f"target coverage declarations valid: {report['core_total']} Core IDs ({report['in_scope']} in scope, {report['out_of_scope']} out of scope; mapping implementation not checked)")
        elif args.command=="check-target-mappings":
            report=check_target_mappings(args.mapping,args.registry,coverage_path=args.coverage)
            if args.format=="json": print(json.dumps(report,ensure_ascii=False,indent=2))
            else:
                coverage_note="coverage declarations matched; " if "coverage" in report else ""
                print(f"mapping structure valid: {report['mapping_count']} hook(s), {report['target_instruction_count']} target instruction(s); {len(report['core_ids_without_mapping'])} Core hook(s) omitted; {coverage_note}semantics not checked")
        elif args.command=="check-target-matrix":
            report=check_target_matrix(args.manifests,args.registry)
            required=", ".join(name for name in ("x64", "arm64", "riscv") if name in report["architectures"])
            if args.format=="json": print(json.dumps(report,ensure_ascii=False,indent=2))
            else: print(f"target coverage declarations valid: required targets {required}; {report['manifest_count']} manifest(s)")
        elif args.command=="scaffold-target-coverage":
            manifest=build_target_coverage_template(args.architecture,args.profile,args.registry)
            print(json.dumps(manifest,ensure_ascii=False,indent=2))
        else:
            program=read(args.file) if args.ir_json else parse_program(args.file.read_text(encoding="utf-8"))
            analyzer=ProgramAnalyzer()
            report=analyzer.analyze(program,profile=args.profile)
            print(json.dumps(report,ensure_ascii=False,indent=2) if args.format=="json" else analyzer.format_text(report))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"assam: error: {exc}", file=sys.stderr)
        return 2
    return 0
if __name__=="__main__": raise SystemExit(main())
