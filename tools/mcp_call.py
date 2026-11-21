"""Call a Hermes-configured MCP server directly over stdio (no chat tool registry needed).

usage: mcp_call.py SERVER list
       mcp_call.py SERVER call TOOL '{"arg": ...}' [TOOL '{...}' ...]
Reads command/args/env for SERVER from `hermes config get mcp_servers.SERVER --json`-equivalent YAML.
"""
import asyncio, json, os, subprocess, sys
import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def server_params(name):
    cfg = yaml.safe_load(open(os.path.expanduser("~/.hermes/config.yaml")))["mcp_servers"][name]
    env = {**os.environ, **{k: str(v) for k, v in (cfg.get("env") or {}).items()}}
    return StdioServerParameters(command=cfg["command"], args=cfg.get("args") or [], env=env)


async def main():
    name, mode, *rest = sys.argv[1:]
    async with stdio_client(server_params(name)) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            if mode == "list":
                for t in (await s.list_tools()).tools:
                    print(t.name, "-", (t.description or "").split("\n")[0][:100])
                return
            if mode == "schema":
                for t in (await s.list_tools()).tools:
                    if t.name in rest:
                        sch = getattr(t, "input_schema", None) or getattr(t, "inputSchema", {})
                        print(t.name, json.dumps(sch.get("properties", {})))
                return
            for tool, args in zip(rest[::2], rest[1::2]):
                res = await s.call_tool(tool, json.loads(args))
                for c in res.content:
                    if c.type == "text":
                        print(f"== {tool}{' [ERROR]' if getattr(res, 'is_error', getattr(res, 'isError', False)) else ''}\n{c.text[:3000]}")
                    elif c.type == "image":
                        import base64, pathlib
                        p = pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / f"{tool}.png"
                        p.write_bytes(base64.b64decode(c.data)); print(f"== {tool} image: {p}")


if __name__ == "__main__":
    asyncio.run(main())
