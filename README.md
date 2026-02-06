# apick

fzf-powered OpenAPI API client.

Browse, search, and call any OpenAPI endpoint from the terminal.

## Install

```
uvx --from git+https://github.com/ralph089/apick apick <spec-url-or-file>
```

Or install globally:

```
uv tool install git+https://github.com/ralph089/apick
```

## Usage

```
apick <spec-url-or-file> [--token TOKEN] [--base-url URL] [--dry-run]
apick --history [--token TOKEN] [--dry-run]
```

- `--token` — Bearer token (or set `APICK_TOKEN` env var)
- `--base-url` — Override the base URL from the spec
- `--dry-run` — Print the curl command without executing
- `--history` — Browse and replay past requests (saved to `~/.apick/history.json`)

## Requirements

- Python 3.10+
- [fzf](https://github.com/junegunn/fzf)
- Optional: [jq](https://jqlang.github.io/jq/) for syntax-highlighted JSON output

## Development

```
git clone https://github.com/ralph089/apick.git
cd apick
uv run apick.py <spec-url-or-file>
```

## License

MIT
