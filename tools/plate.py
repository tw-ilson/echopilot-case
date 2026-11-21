"""Automate the print plate: pull A1 presets from the running OrcaSlicer (MCP plugin), slice both case
halves headlessly with OrcaSlicer's CLI (arrange + orient), save print/echopilot_case.3mf, open it in the GUI.

usage: uv run --with mcp --with pyyaml python tools/plate.py
"""
import asyncio, glob, json, os, pathlib, subprocess, sys

sys.path.insert(0, os.path.dirname(__file__))
from mcp_call import ClientSession, server_params, stdio_client  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRINT = ROOT / "print"
WORK = pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / "echopilot-plate"
APPIMAGE = pathlib.Path.home() / "AppImages/orcaslicer.appimage"
PRESETS = {  # type -> preset name
    "printer": "Bambu Lab A1 0.4 nozzle",
    "print": "0.20mm Standard @BBL A1",
    "filament": "Bambu PLA Basic @BBL A1",
}
PARTS = [PRINT / "echopilot_case_bottom.stl", PRINT / "echopilot_case_top.stl"]
OUT = PRINT / "echopilot_case.3mf"


async def fetch_presets():
    async with stdio_client(server_params("orcaslicer")) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            got = {}
            for typ, name in PRESETS.items():
                res = await s.call_tool("get_preset_config", {"type": typ, "name": name})
                data = json.loads(res.content[0].text)
                if "error" in data:
                    sys.exit(f"{typ} preset {name!r}: {data['error']}")
                got[typ] = data
            return got


def to_cli_json(typ, name, data):
    cfg = data.get("config", data.get("settings", data))
    cfg = {k: v for k, v in cfg.items() if k not in ("inherits", "base_id")}
    cfg.update({"type": {"printer": "machine", "print": "process"}.get(typ, typ), "name": name, "from": "User"})
    return cfg


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    presets = asyncio.run(fetch_presets())
    files = {}
    for typ, data in presets.items():
        f = WORK / f"{typ}.json"
        f.write_text(json.dumps(to_cli_json(typ, PRESETS[typ], data), indent=1))
        files[typ] = f
    cmd = [str(APPIMAGE), "--appimage-extract-and-run",
           "--load-settings", f"{files['printer']};{files['print']}",
           "--load-filaments", str(files["filament"]),
           "--arrange", "1", "--orient", "0", "--slice", "0",
           "--export-3mf", OUT.name, "--outputdir", str(WORK), *map(str, PARTS)]
    print("$", " ".join(cmd))
    p = subprocess.run(cmd, capture_output=True, text=True)
    tail = "\n".join((p.stdout + p.stderr).splitlines()[-25:])
    built = WORK / OUT.name
    if p.returncode != 0 or not built.exists():
        sys.exit(f"orca CLI failed ({p.returncode}):\n{tail}")
    built.replace(OUT)
    rj = WORK / "result.json"
    print(rj.read_text() if rj.exists() else tail)
    print("wrote", OUT, OUT.stat().st_size, "bytes; gcode:", glob.glob(str(WORK / "*.gcode")))


if __name__ == "__main__":
    main()
