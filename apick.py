"""apick — fzf-powered OpenAPI API client."""

__version__ = "0.0.0"

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from urllib.parse import urlencode, urlparse

import httpx
import yaml

HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".apick", "history.json")
MAX_HISTORY = 500


def highlight_json(text: str) -> str:
    """Colorize JSON text via jq. Falls back to plain text if jq is unavailable."""
    try:
        result = subprocess.run(
            ["jq", "-C", "."],
            input=text,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout
    except FileNotFoundError:
        pass
    return text


def fetch_spec(source: str) -> dict:
    """Fetch and parse an OpenAPI spec from a URL or local file."""
    if urlparse(source).scheme in ("http", "https"):
        resp = httpx.get(source, timeout=30)
        resp.raise_for_status()
        content = resp.text
    else:
        with open(source) as f:
            content = f.read()

    # Try JSON first, fall back to YAML
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return yaml.safe_load(content)


def resolve_ref(spec: dict, ref: str) -> dict:
    """Resolve a $ref pointer like '#/components/schemas/Pet'."""
    parts = ref.lstrip("#/").split("/")
    node = spec
    for part in parts:
        node = node[part]
    return node


def resolve_schema(spec: dict, schema: dict) -> dict:
    """Recursively resolve $ref in a schema."""
    if not isinstance(schema, dict):
        return schema
    if "$ref" in schema:
        schema = resolve_ref(spec, schema["$ref"])
    result = {}
    for k, v in schema.items():
        if k == "properties" and isinstance(v, dict):
            result[k] = {pk: resolve_schema(spec, pv) for pk, pv in v.items()}
        elif k == "items" and isinstance(v, dict):
            result[k] = resolve_schema(spec, v)
        elif k == "allOf" and isinstance(v, list):
            merged = {}
            for item in v:
                resolved = resolve_schema(spec, item)
                merged.update(resolved)
            return merged
        else:
            result[k] = v
    return result


def extract_endpoints(spec: dict) -> list[dict]:
    """Walk spec paths and build a flat list of endpoints."""
    endpoints = []
    for path, methods in spec.get("paths", {}).items():
        # Collect path-level parameters
        path_params = methods.get("parameters", [])
        for method in ("get", "post", "put", "patch", "delete", "head", "options"):
            if method not in methods:
                continue
            operation = methods[method]
            # Merge path-level and operation-level parameters
            op_params = operation.get("parameters", [])
            # Resolve any $ref parameters
            resolved_params = []
            for p in path_params + op_params:
                if "$ref" in p:
                    p = resolve_ref(spec, p["$ref"])
                resolved_params.append(p)

            endpoints.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "summary": operation.get("summary", ""),
                    "description": operation.get("description", ""),
                    "operationId": operation.get("operationId", ""),
                    "parameters": resolved_params,
                    "requestBody": operation.get("requestBody"),
                    "responses": operation.get("responses", {}),
                }
            )
    return endpoints


def format_for_fzf(endpoints: list[dict]) -> str:
    """Format endpoint list for fzf display."""
    lines = []
    max_method = max((len(ep["method"]) for ep in endpoints), default=6)
    max_path = max((len(ep["path"]) for ep in endpoints), default=20)
    for i, ep in enumerate(endpoints):
        method = ep["method"].ljust(max_method)
        path = ep["path"].ljust(max_path)
        summary = ep["summary"]
        # Color the method
        colors = {
            "GET": "\033[32m",
            "POST": "\033[33m",
            "PUT": "\033[34m",
            "PATCH": "\033[35m",
            "DELETE": "\033[31m",
        }
        color = colors.get(ep["method"], "\033[0m")
        reset = "\033[0m"
        lines.append(f"{i:04d} {color}{method}{reset} {path} {summary}")
    return "\n".join(lines)


def endpoint_detail(spec: dict, ep: dict) -> str:
    """Format detail string for fzf preview pane."""
    lines = []
    lines.append(f"\033[1m{ep['method']} {ep['path']}\033[0m")
    if ep["summary"]:
        lines.append(f"  {ep['summary']}")
    if ep["description"]:
        lines.append(f"\n  {ep['description']}")
    lines.append("")

    # Parameters
    params = ep.get("parameters", [])
    if params:
        lines.append("\033[1mParameters:\033[0m")
        for p in params:
            required = " (required)" if p.get("required") else ""
            schema = p.get("schema", {})
            ptype = schema.get("type", "string")
            desc = p.get("description", "")
            lines.append(f"  \033[36m{p.get('in', '?'):6s}\033[0m {p['name']}: {ptype}{required}")
            if desc:
                lines.append(f"           {desc}")
        lines.append("")

    # Request body
    rb = ep.get("requestBody")
    if rb:
        lines.append("\033[1mRequest Body:\033[0m")
        content = rb.get("content", {})
        for media, media_obj in content.items():
            lines.append(f"  Content-Type: {media}")
            schema = media_obj.get("schema", {})
            resolved = resolve_schema(spec, schema)
            lines.append("  Schema:")
            lines.append(format_schema_tree(resolved, indent=4))
        lines.append("")

    # Responses
    if ep.get("responses"):
        lines.append("\033[1mResponses:\033[0m")
        for code, resp in ep["responses"].items():
            desc = resp.get("description", "") if isinstance(resp, dict) else ""
            lines.append(f"  \033[33m{code}\033[0m {desc}")
            if isinstance(resp, dict):
                content = resp.get("content", {})
                for media_obj in content.values():
                    schema = media_obj.get("schema", {})
                    resolved = resolve_schema(spec, schema)
                    lines.append(format_schema_tree(resolved, indent=4))

    return "\n".join(lines)


def format_schema_tree(schema: dict, indent: int = 0) -> str:
    """Format a JSON schema as a readable tree."""
    if not isinstance(schema, dict):
        return " " * indent + str(schema)
    lines = []
    pad = " " * indent
    stype = schema.get("type", "object")

    if stype == "object":
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        if not props:
            lines.append(f"{pad}{{object}}")
        for name, prop in props.items():
            req = "*" if name in required else " "
            ptype = prop.get("type", "object")
            desc = prop.get("description", "")
            if ptype == "object" and prop.get("properties"):
                lines.append(f"{pad}{req} {name}: {{")
                lines.append(format_schema_tree(prop, indent + 4))
                lines.append(f"{pad}  }}")
            elif ptype == "array":
                items = prop.get("items", {})
                items_type = items.get("type", "object")
                lines.append(f"{pad}{req} {name}: [{items_type}]")
                if items.get("properties"):
                    lines.append(format_schema_tree(items, indent + 4))
            else:
                extra = f"  -- {desc}" if desc else ""
                lines.append(f"{pad}{req} {name}: {ptype}{extra}")
    elif stype == "array":
        items = schema.get("items", {})
        lines.append(f"{pad}[array of {items.get('type', 'object')}]")
        if items.get("properties"):
            lines.append(format_schema_tree(items, indent + 2))
    else:
        lines.append(f"{pad}{stype}")

    return "\n".join(lines)


def pick_endpoint(endpoints: list[dict], spec: dict, script_path: str) -> dict | None:
    """Shell out to fzf and return the selected endpoint."""
    fzf_input = format_for_fzf(endpoints)

    # Write spec to temp file to avoid command line length limits
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="apick_spec_", delete=False
    ) as spec_file:
        json.dump(spec, spec_file)
        spec_file_name = spec_file.name

    try:
        preview_cmd = (
            f"{sys.executable} {script_path} --_preview {{1}} --_spec-file {spec_file_name}"
        )
        try:
            result = subprocess.run(
                [
                    "fzf",
                    "--ansi",
                    "--reverse",
                    "--nth", "2..",
                    "--with-nth", "2..",
                    "--border", "rounded",
                    "--border-label", " apick ",
                    "--pointer", "▶",
                    "--header",
                    "Select an endpoint (type to search)",
                    "--preview",
                    preview_cmd,
                    "--preview-window",
                    "right:50%:wrap",
                ],
                input=fzf_input,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            print(
                "\033[31mError: fzf not found. Install it: brew install fzf\033[0m", file=sys.stderr
            )
            sys.exit(1)
    finally:
        os.unlink(spec_file_name)

    if result.returncode != 0:
        return None  # User cancelled

    line = result.stdout.strip()
    if not line:
        return None
    idx = int(line.split()[0])
    return endpoints[idx]


def collect_params(spec: dict, ep: dict) -> dict:
    """Prompt for path/query/header params and request body."""
    collected = {"path": {}, "query": {}, "header": {}, "body": None}
    params = ep.get("parameters", [])

    for p in params:
        location = p.get("in", "query")
        name = p["name"]
        required = p.get("required", False)
        schema = p.get("schema", {})
        ptype = schema.get("type", "string")
        default = schema.get("default")
        description = p.get("description", "")

        if location == "path":
            # Always required
            hint = f" ({description})" if description else ""
            while True:
                val = input(f"  \033[36m{name}\033[0m [{ptype}]{hint}: ").strip()
                if val:
                    break
                print(f"  \033[31m{name} is required\033[0m")
            collected["path"][name] = val
        elif location == "query":
            tag = "" if required else " (optional, Enter to skip)"
            default_hint = f" [default: {default}]" if default else ""
            desc_hint = f" ({description})" if description else ""
            val = input(
                f"  \033[36m{name}\033[0m [{ptype}]{desc_hint}{default_hint}{tag}: "
            ).strip()
            if val:
                collected["query"][name] = val
            elif required and default is not None:
                collected["query"][name] = str(default)
            elif required:
                while not val:
                    val = input(f"  \033[31m{name} is required\033[0m: ").strip()
                collected["query"][name] = val
        elif location == "header":
            tag = "" if required else " (optional, Enter to skip)"
            val = input(f"  \033[36m{name}\033[0m [header]{tag}: ").strip()
            if val:
                collected["header"][name] = val
            elif required:
                while not val:
                    val = input(f"  \033[31m{name} is required\033[0m: ").strip()
                collected["header"][name] = val

    # Request body
    rb = ep.get("requestBody")
    if rb:
        content = rb.get("content", {})
        json_content = content.get("application/json")
        if json_content:
            schema = json_content.get("schema", {})
            resolved = resolve_schema(spec, schema)
            template = generate_template(resolved)
            body_json = edit_body(template)
            if body_json is not None:
                collected["body"] = body_json

    return collected


def generate_template(schema: dict) -> dict | list | str:
    """Generate a JSON template with placeholder values from a schema."""
    stype = schema.get("type", "object")
    if stype == "object":
        props = schema.get("properties", {})
        obj = {}
        for name, prop in props.items():
            obj[name] = generate_template(prop)
        return obj
    if stype == "array":
        items = schema.get("items", {})
        return [generate_template(items)]
    if stype == "integer":
        return schema.get("example", schema.get("default", 0))
    if stype == "number":
        return schema.get("example", schema.get("default", 0.0))
    if stype == "boolean":
        return schema.get("example", schema.get("default", False))
    if stype == "string":
        if schema.get("enum"):
            return schema["enum"][0]
        return schema.get("example", schema.get("default", ""))
    return ""


def edit_body(template: object) -> object | None:
    """Open template in $EDITOR for the user to fill in."""
    editor = os.environ.get("EDITOR", "vim")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", prefix="apick_", delete=False) as f:
        json.dump(template, f, indent=2)
        f.write("\n")
        tmpfile = f.name

    try:
        print(f"\n  Opening {editor} to edit request body...")
        subprocess.run([editor, tmpfile], check=True)
        with open(tmpfile) as f:
            return json.load(f)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"\033[31mError editing body: {e}\033[0m", file=sys.stderr)
        return None
    finally:
        os.unlink(tmpfile)


def get_base_url(spec: dict, spec_source: str, override: str | None = None) -> str:
    """Extract base URL from spec or use override.

    Handles relative server URLs by combining with the spec source URL.
    """
    if override:
        return override.rstrip("/")
    servers = spec.get("servers", [])
    if servers:
        server_url = servers[0]["url"].rstrip("/")
        parsed = urlparse(server_url)
        if parsed.scheme:
            return server_url
        # Relative URL — derive base from spec source
        source_parsed = urlparse(spec_source)
        if source_parsed.scheme:
            return f"{source_parsed.scheme}://{source_parsed.netloc}{server_url}"
        return server_url
    return ""


def build_curl(
    method: str,
    url: str,
    headers: dict[str, str],
    body: object | None = None,
) -> str:
    """Build equivalent curl command string."""
    parts = ["curl", "-s"]
    if method != "GET":
        parts.extend(["-X", method])
    for k, v in headers.items():
        parts.extend(["-H", f"'{k}: {v}'"])
    if body is not None:
        parts.extend(["-H", "'Content-Type: application/json'"])
        parts.extend(["-d", f"'{json.dumps(body)}'"])
    parts.append(f'"{url}"')
    return " ".join(parts)


def execute_request(
    method: str,
    url: str,
    headers: dict[str, str],
    body: object | None = None,
) -> int:
    """Make the HTTP request and print results. Returns HTTP status code."""
    kwargs: dict = {"headers": headers, "timeout": 30}
    if body is not None:
        kwargs["json"] = body

    resp = httpx.request(method, url, **kwargs)

    # Status line
    color = "\033[32m" if resp.status_code < 400 else "\033[31m"
    print(f"\n{color}{resp.status_code} {resp.reason_phrase}\033[0m")

    # Response body
    ct = resp.headers.get("content-type", "")
    if "json" in ct:
        try:
            formatted = json.dumps(resp.json(), indent=2)
            print(highlight_json(formatted))
        except Exception:
            print(resp.text)
    else:
        print(resp.text)

    return resp.status_code


def load_history() -> list[dict]:
    """Read history file. Returns [] on any error."""
    try:
        with open(HISTORY_FILE) as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def save_history(entries: list[dict]) -> None:
    """Write entries to disk, truncating to MAX_HISTORY."""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    entries = entries[-MAX_HISTORY:]
    with open(HISTORY_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def format_history_for_fzf(entries: list[dict]) -> str:
    """Format history entries for fzf display, newest first."""
    colors = {
        "GET": "\033[32m",
        "POST": "\033[33m",
        "PUT": "\033[34m",
        "PATCH": "\033[35m",
        "DELETE": "\033[31m",
    }
    reset = "\033[0m"
    lines = []
    reversed_entries = list(reversed(entries))
    for i, entry in enumerate(reversed_entries):
        real_idx = len(entries) - 1 - i
        method = entry.get("method", "?")
        color = colors.get(method, reset)
        ts = entry.get("timestamp", "")[:16]
        status = entry.get("status_code")
        status_str = "err" if status is None else str(status)
        url = entry.get("url", "")
        summary = entry.get("summary", "")
        lines.append(
            f"{real_idx:04d} {ts}  {color}{method:7s}{reset} [{status_str:>3s}] {url}  {summary}"
        )
    return "\n".join(lines)


def pick_history_entry(entries: list[dict]) -> dict | None:
    """Open fzf over history entries and return the selected one."""
    fzf_input = format_history_for_fzf(entries)
    try:
        result = subprocess.run(
            [
                "fzf",
                "--ansi",
                "--reverse",
                "--nth", "2..",
                "--with-nth", "2..",
                "--border", "rounded",
                "--border-label", " history ",
                "--pointer", "▶",
                "--header",
                "Select a request to replay (type to search)",
                "--preview",
                "echo {2..}",
                "--preview-window",
                "down:3:wrap",
            ],
            input=fzf_input,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print(
            "\033[31mError: fzf not found. Install it: brew install fzf\033[0m",
            file=sys.stderr,
        )
        sys.exit(1)

    if result.returncode != 0:
        return None

    line = result.stdout.strip()
    if not line:
        return None
    idx = int(line.split()[0])
    return entries[idx]


def _save_to_history(
    method: str,
    url: str,
    headers: dict[str, str],
    body: object | None,
    spec_source: str,
    summary: str,
    status_code: int | None,
) -> None:
    """Append one entry to history, stripping Authorization header."""
    safe_headers = {k: v for k, v in headers.items() if k.lower() != "authorization"}
    entry = {
        "method": method,
        "url": url,
        "headers": safe_headers,
        "body": body,
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "spec_source": spec_source,
        "summary": summary,
        "status_code": status_code,
    }
    entries = load_history()
    entries.append(entry)
    save_history(entries)


def handle_preview(index: str, spec: dict, endpoints: list[dict]) -> None:
    """Handle --_preview mode: print endpoint details for fzf preview pane."""
    idx = int(index)
    if 0 <= idx < len(endpoints):
        print(endpoint_detail(spec, endpoints[idx]))


def main():
    parser = argparse.ArgumentParser(
        description="apick - fzf-powered OpenAPI API client",
        usage="apick <spec-url-or-file> [options]",
    )
    parser.add_argument("spec", nargs="?", help="OpenAPI spec URL or local file path")
    parser.add_argument("--token", help="Bearer token (or set APICK_TOKEN env var)")
    parser.add_argument("--base-url", help="Override base URL from spec")
    parser.add_argument("--dry-run", action="store_true", help="Print curl command only")
    parser.add_argument("--history", action="store_true", help="Browse and replay past requests")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Internal flags for fzf preview
    parser.add_argument("--_preview", help=argparse.SUPPRESS)
    parser.add_argument("--_spec-file", help=argparse.SUPPRESS)

    args = parser.parse_args()

    # Handle preview mode (called by fzf)
    if args._preview is not None:
        if args._spec_file is None:
            sys.exit(1)
        with open(args._spec_file) as f:
            spec = json.load(f)
        endpoints = extract_endpoints(spec)
        handle_preview(args._preview, spec, endpoints)
        sys.exit(0)

    if args.history:
        entries = load_history()
        if not entries:
            print("\033[33mNo history yet.\033[0m", file=sys.stderr)
            sys.exit(0)
        entry = pick_history_entry(entries)
        if entry is None:
            sys.exit(0)
        assert entry is not None  # noqa: S101 — narrowing for ty
        method = entry["method"]
        url = entry["url"]
        headers = dict(entry.get("headers", {}))
        body = entry.get("body")
        token = args.token or os.environ.get("APICK_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        curl_cmd = build_curl(method, url, headers, body)
        print(f"\n\033[2m$ {curl_cmd}\033[0m")
        if args.dry_run:
            return
        try:
            execute_request(method, url, headers, body)
        except httpx.HTTPError as e:
            print(f"\n\033[31mRequest failed: {e}\033[0m", file=sys.stderr)
            sys.exit(1)
        return

    if not args.spec:
        parser.print_help()
        sys.exit(1)

    # Fetch and parse spec
    try:
        spec = fetch_spec(args.spec)
    except Exception as e:
        print(f"\033[31mFailed to load spec: {e}\033[0m", file=sys.stderr)
        sys.exit(1)

    # Extract endpoints
    endpoints = extract_endpoints(spec)
    if not endpoints:
        print("\033[31mNo endpoints found in spec\033[0m", file=sys.stderr)
        sys.exit(1)

    # Pick endpoint with fzf
    ep = pick_endpoint(endpoints, spec, os.path.abspath(__file__))
    if ep is None:
        sys.exit(0)  # User cancelled
    assert ep is not None  # noqa: S101 — narrowing for ty

    print(f"\n\033[1m{ep['method']} {ep['path']}\033[0m")
    if ep["summary"]:
        print(f"  {ep['summary']}\n")

    # Collect parameters
    collected = collect_params(spec, ep)

    # Build URL
    base_url = get_base_url(spec, args.spec, args.base_url)
    path = ep["path"]
    for name, val in collected["path"].items():
        path = path.replace(f"{{{name}}}", val)
    url = base_url + path
    if collected["query"]:
        url += "?" + urlencode(collected["query"])

    # Build headers
    headers: dict[str, str] = {}
    token = args.token or os.environ.get("APICK_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers.update(collected["header"])

    body = collected["body"]

    # Print curl command
    curl_cmd = build_curl(ep["method"], url, headers, body)
    print(f"\n\033[2m$ {curl_cmd}\033[0m")
    if body is not None:
        print(highlight_json(json.dumps(body, indent=2)))

    if args.dry_run:
        return

    # Execute request
    try:
        status_code = execute_request(ep["method"], url, headers, body)
        _save_to_history(ep["method"], url, headers, body, args.spec, ep["summary"], status_code)
    except httpx.HTTPError as e:
        _save_to_history(ep["method"], url, headers, body, args.spec, ep["summary"], None)
        print(f"\n\033[31mRequest failed: {e}\033[0m", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
