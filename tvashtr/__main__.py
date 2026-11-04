"""tvashtr CLI.

  python -m tvashtr bench    --model qwen3-coder:30b --strategy adaptive [--part test|dev|all] [--limit N]
  python -m tvashtr autotune --model qwen3-coder:30b [--limit N]      # pick the best PTE on the dev split
  python -m tvashtr serve    [--port 11435]                           # Ollama-compatible enhanced endpoint
  python -m tvashtr expo     --base DIR --instruct DIR --alpha 0.3 --out DIR [--donor DIR:BETA ...]
  python -m tvashtr import   --dir DIR --name NAME [--quantize q4_K_M]
"""
import argparse
import json


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("bench")
    b.add_argument("--model", required=True)
    b.add_argument("--strategy", default="adaptive")
    b.add_argument("--part", default="test", choices=["dev", "test", "all"])
    b.add_argument("--limit", type=int)
    b.add_argument("--workers", type=int, default=2)
    b.add_argument("--params", default="{}", help='JSON strategy params, e.g. {"n": 6}')

    t = sub.add_parser("autotune")
    t.add_argument("--model", required=True)
    t.add_argument("--limit", type=int)
    t.add_argument("--strategies", default="direct,plan,self_debug,codet,s_star,adaptive")
    t.add_argument("--workers", type=int, default=2)

    s = sub.add_parser("serve")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=11435)

    e = sub.add_parser("expo")
    e.add_argument("--base", required=True)
    e.add_argument("--instruct", required=True)
    e.add_argument("--alpha", type=float, default=0.3)
    e.add_argument("--out", required=True)
    e.add_argument("--donor", action="append", default=[], help="DIR:BETA task vector to add (same family)")
    e.add_argument("--exclude", default="", help="regex of tensor names to leave as instruct")

    g = sub.add_parser("expo-gguf", help="ExPO on fp16 GGUFs (Ollama tags or paths), then ollama create")
    g.add_argument("--base", required=True, help="e.g. qwen2.5-coder:7b-base-fp16 or a .gguf path")
    g.add_argument("--instruct", required=True, help="e.g. qwen2.5-coder:7b-instruct-fp16 or a .gguf path")
    g.add_argument("--alpha", type=float, default=0.3)
    g.add_argument("--out", required=True, help="output .gguf path")
    g.add_argument("--name", help="Ollama model name to create from the result")
    g.add_argument("--quantize", help="e.g. q4_K_M or q8_0 (as supported by your Ollama)")
    g.add_argument("--donor", action="append", default=[], help="TAG_OR_PATH:BETA task vector to add")
    g.add_argument("--exclude", default="")

    w = sub.add_parser("expo-sweep", help="controlled ExPO experiment: control + alphas, dev select, test confirm")
    w.add_argument("--base", required=True)
    w.add_argument("--instruct", required=True)
    w.add_argument("--alphas", default="0.1,0.3,0.5")
    w.add_argument("--prefix", required=True, help="Ollama name prefix for created models, e.g. qc7")
    w.add_argument("--quantize", default="q8_0")
    w.add_argument("--workdir", default="models")
    w.add_argument("--limit", type=int)
    w.add_argument("--workers", type=int, default=2)

    i = sub.add_parser("import")
    i.add_argument("--dir", required=True)
    i.add_argument("--name", required=True)
    i.add_argument("--quantize", default="int8", help="int4|int8|... (as supported by your Ollama)")

    a = ap.parse_args()
    if a.cmd == "bench":
        from . import bench
        print(json.dumps(bench.run(a.model, a.strategy, a.part, a.limit, a.workers, json.loads(a.params)), indent=2))
    elif a.cmd == "autotune":
        from . import autotune
        print(json.dumps(autotune.tune(a.model, a.strategies.split(","), a.limit, a.workers), indent=2))
    elif a.cmd == "serve":
        from . import server
        server.serve(a.host, a.port)
    elif a.cmd == "expo":
        from . import weights
        donors = [(d.rsplit(":", 1)[0], float(d.rsplit(":", 1)[1])) for d in a.donor]
        weights.expo(a.base, a.instruct, a.out, a.alpha, donors, a.exclude or None)
    elif a.cmd == "expo-gguf":
        from pathlib import Path

        from . import weights

        def resolve(x):
            return Path(x) if Path(x).is_file() else weights.ollama_blob(x)

        donors = [(resolve(d.rsplit(":", 1)[0]), float(d.rsplit(":", 1)[1])) for d in a.donor]
        out = weights.expo_gguf(resolve(a.base), resolve(a.instruct), a.out, a.alpha, donors, a.exclude or None)
        if a.name:
            tmpl = None if Path(a.instruct).is_file() else a.instruct
            weights.ollama_create_gguf(out, a.name, template_from=tmpl, quantize=a.quantize)
    elif a.cmd == "expo-sweep":
        from . import sweep
        alphas = [float(x) for x in a.alphas.split(",")]
        print(json.dumps(sweep.sweep(a.base, a.instruct, alphas, a.prefix, a.quantize or None, a.workdir,
                                     a.limit, a.workers), indent=2))
    elif a.cmd == "import":
        from . import weights
        weights.ollama_import(a.dir, a.name, a.quantize)


if __name__ == "__main__":
    main()
