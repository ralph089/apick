"""Tests for apick — pure functions only (no fzf/stdin needed)."""

import json
from unittest.mock import MagicMock, patch

import apick

# ---------------------------------------------------------------------------
# resolve_ref / resolve_schema
# ---------------------------------------------------------------------------


class TestResolveRef:
    def test_simple_ref(self):
        spec = {"components": {"schemas": {"Pet": {"type": "object"}}}}
        result = apick.resolve_ref(spec, "#/components/schemas/Pet")
        assert result == {"type": "object"}

    def test_nested_ref(self):
        spec = {
            "components": {
                "schemas": {
                    "Pet": {"$ref": "#/components/schemas/Animal"},
                    "Animal": {"type": "object", "properties": {"name": {"type": "string"}}},
                }
            }
        }
        # resolve_ref itself doesn't recurse — it just follows one pointer
        result = apick.resolve_ref(spec, "#/components/schemas/Pet")
        assert "$ref" in result


class TestResolveSchema:
    def test_resolves_ref(self):
        spec = {"components": {"schemas": {"Pet": {"type": "object"}}}}
        schema = {"$ref": "#/components/schemas/Pet"}
        result = apick.resolve_schema(spec, schema)
        assert result == {"type": "object"}

    def test_resolves_nested_ref_chain(self):
        # resolve_schema follows the first $ref, then resolves keys in the result;
        # a second-level $ref in a non-special key is kept as-is
        spec = {
            "components": {
                "schemas": {
                    "Pet": {"$ref": "#/components/schemas/Animal"},
                    "Animal": {"type": "object"},
                }
            }
        }
        schema = {"$ref": "#/components/schemas/Pet"}
        result = apick.resolve_schema(spec, schema)
        # After resolving Pet → {"$ref": "...Animal"}, the inner $ref key
        # is not a special key so it passes through
        assert "$ref" in result

    def test_allof_merging(self):
        # allOf merging uses dict.update, so all items contribute keys
        spec = {}
        schema = {
            "allOf": [
                {"type": "object"},
                {"properties": {"name": {"type": "string"}}},
            ]
        }
        result = apick.resolve_schema(spec, schema)
        assert result["type"] == "object"
        assert "name" in result["properties"]

    def test_non_dict_passthrough(self):
        assert apick.resolve_schema({}, "string") == "string"
        assert apick.resolve_schema({}, 42) == 42


# ---------------------------------------------------------------------------
# extract_endpoints
# ---------------------------------------------------------------------------


class TestExtractEndpoints:
    def test_basic_get_post(self):
        spec = {
            "paths": {
                "/pets": {
                    "get": {"summary": "List pets"},
                    "post": {"summary": "Create pet"},
                }
            }
        }
        eps = apick.extract_endpoints(spec)
        assert len(eps) == 2
        assert eps[0]["method"] == "GET"
        assert eps[0]["path"] == "/pets"
        assert eps[0]["summary"] == "List pets"
        assert eps[1]["method"] == "POST"

    def test_merges_path_and_operation_params(self):
        spec = {
            "paths": {
                "/pets/{id}": {
                    "parameters": [{"name": "id", "in": "path"}],
                    "get": {
                        "summary": "Get pet",
                        "parameters": [{"name": "fields", "in": "query"}],
                    },
                }
            }
        }
        eps = apick.extract_endpoints(spec)
        assert len(eps) == 1
        names = [p["name"] for p in eps[0]["parameters"]]
        assert "id" in names
        assert "fields" in names

    def test_resolves_ref_parameters(self):
        spec = {
            "components": {
                "parameters": {
                    "LimitParam": {"name": "limit", "in": "query", "schema": {"type": "integer"}}
                }
            },
            "paths": {
                "/items": {
                    "get": {
                        "summary": "List",
                        "parameters": [{"$ref": "#/components/parameters/LimitParam"}],
                    }
                }
            },
        }
        eps = apick.extract_endpoints(spec)
        assert eps[0]["parameters"][0]["name"] == "limit"

    def test_empty_paths(self):
        assert apick.extract_endpoints({"paths": {}}) == []
        assert apick.extract_endpoints({}) == []


# ---------------------------------------------------------------------------
# format_for_fzf
# ---------------------------------------------------------------------------


class TestFormatForFzf:
    def test_alignment_and_indexing(self):
        eps = [
            {"method": "GET", "path": "/pets", "summary": "List pets"},
            {"method": "DELETE", "path": "/pets/{id}", "summary": "Delete pet"},
        ]
        output = apick.format_for_fzf(eps)
        lines = output.split("\n")
        assert len(lines) == 2
        assert lines[0].startswith("0000 ")
        assert lines[1].startswith("0001 ")

    def test_color_codes(self):
        eps = [
            {"method": "GET", "path": "/a", "summary": ""},
            {"method": "POST", "path": "/b", "summary": ""},
            {"method": "DELETE", "path": "/c", "summary": ""},
        ]
        output = apick.format_for_fzf(eps)
        assert "\033[32m" in output  # GET = green
        assert "\033[33m" in output  # POST = yellow
        assert "\033[31m" in output  # DELETE = red


# ---------------------------------------------------------------------------
# format_schema_tree
# ---------------------------------------------------------------------------


class TestFormatSchemaTree:
    def test_object_with_required_and_optional(self):
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
        }
        tree = apick.format_schema_tree(schema)
        assert "* name: string" in tree
        assert "  age: integer" in tree

    def test_nested_object(self):
        schema = {
            "type": "object",
            "properties": {
                "address": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                }
            },
        }
        tree = apick.format_schema_tree(schema)
        assert "address: {" in tree
        assert "city: string" in tree

    def test_array_type(self):
        schema = {"type": "array", "items": {"type": "string"}}
        tree = apick.format_schema_tree(schema)
        assert "[array of string]" in tree

    def test_primitive_type(self):
        tree = apick.format_schema_tree({"type": "string"})
        assert "string" in tree


# ---------------------------------------------------------------------------
# generate_template
# ---------------------------------------------------------------------------


class TestGenerateTemplate:
    def test_object_schema(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
        }
        result = apick.generate_template(schema)
        assert isinstance(result, dict)
        assert result["name"] == ""
        assert result["count"] == 0

    def test_array_schema(self):
        schema = {"type": "array", "items": {"type": "string"}}
        result = apick.generate_template(schema)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_uses_example(self):
        schema = {"type": "string", "example": "Fido"}
        assert apick.generate_template(schema) == "Fido"

    def test_uses_default(self):
        schema = {"type": "integer", "default": 42}
        assert apick.generate_template(schema) == 42

    def test_enum_picks_first(self):
        schema = {"type": "string", "enum": ["active", "inactive"]}
        assert apick.generate_template(schema) == "active"

    def test_boolean_default(self):
        assert apick.generate_template({"type": "boolean"}) is False

    def test_number_default(self):
        assert apick.generate_template({"type": "number"}) == 0.0


# ---------------------------------------------------------------------------
# get_base_url
# ---------------------------------------------------------------------------


class TestGetBaseUrl:
    def test_override_takes_precedence(self):
        spec = {"servers": [{"url": "https://api.example.com"}]}
        result = apick.get_base_url(spec, "spec.yaml", override="https://override.com/")
        assert result == "https://override.com"

    def test_absolute_server_url(self):
        spec = {"servers": [{"url": "https://api.example.com/v1"}]}
        result = apick.get_base_url(spec, "spec.yaml")
        assert result == "https://api.example.com/v1"

    def test_relative_server_url_with_http_source(self):
        spec = {"servers": [{"url": "/api/v1"}]}
        result = apick.get_base_url(spec, "https://example.com/specs/api.yaml")
        assert result == "https://example.com/api/v1"

    def test_relative_server_url_with_file_source(self):
        spec = {"servers": [{"url": "/api/v1"}]}
        result = apick.get_base_url(spec, "spec.yaml")
        assert result == "/api/v1"

    def test_no_servers(self):
        assert apick.get_base_url({}, "spec.yaml") == ""


# ---------------------------------------------------------------------------
# build_curl
# ---------------------------------------------------------------------------


class TestBuildCurl:
    def test_get_without_body(self):
        cmd = apick.build_curl("GET", "https://api.example.com/pets", {})
        assert cmd.startswith("curl -s")
        assert "-X" not in cmd
        assert '"https://api.example.com/pets"' in cmd

    def test_post_with_body_and_headers(self):
        cmd = apick.build_curl(
            "POST",
            "https://api.example.com/pets",
            {"Authorization": "Bearer tok123"},
            body={"name": "Fido"},
        )
        assert "-X POST" in cmd
        assert "'Authorization: Bearer tok123'" in cmd
        assert "'Content-Type: application/json'" in cmd
        assert "-d" in cmd
        assert "Fido" in cmd

    def test_token_in_headers(self):
        cmd = apick.build_curl(
            "GET",
            "https://api.example.com/pets",
            {"Authorization": "Bearer secret"},
        )
        assert "'Authorization: Bearer secret'" in cmd


# ---------------------------------------------------------------------------
# fetch_spec (with mocking)
# ---------------------------------------------------------------------------


class TestFetchSpec:
    def test_load_json_file(self, tmp_path):
        spec_data = {"openapi": "3.0.0", "paths": {}}
        p = tmp_path / "spec.json"
        p.write_text(json.dumps(spec_data))
        result = apick.fetch_spec(str(p))
        assert result == spec_data

    def test_load_yaml_file(self, tmp_path):
        p = tmp_path / "spec.yaml"
        p.write_text("openapi: '3.0.0'\npaths: {}\n")
        result = apick.fetch_spec(str(p))
        assert result["openapi"] == "3.0.0"

    def test_load_from_url(self):
        spec_data = {"openapi": "3.0.0", "paths": {}}
        mock_resp = MagicMock()
        mock_resp.text = json.dumps(spec_data)
        mock_resp.raise_for_status = MagicMock()

        with patch("apick.httpx.get", return_value=mock_resp) as mock_get:
            result = apick.fetch_spec("https://example.com/spec.json")
            mock_get.assert_called_once_with("https://example.com/spec.json", timeout=30)
            assert result == spec_data


# ---------------------------------------------------------------------------
# highlight_json (with mocking)
# ---------------------------------------------------------------------------


class TestHighlightJson:
    def test_jq_available(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{\n  "key": "value"\n}\n'

        with patch("apick.subprocess.run", return_value=mock_result):
            result = apick.highlight_json('{"key": "value"}')
            assert result == mock_result.stdout

    def test_jq_not_found(self):
        with patch("apick.subprocess.run", side_effect=FileNotFoundError):
            result = apick.highlight_json('{"key": "value"}')
            assert result == '{"key": "value"}'


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class TestHistory:
    def test_load_missing_file(self, tmp_path):
        with patch("apick.HISTORY_FILE", str(tmp_path / "nonexistent.json")):
            assert apick.load_history() == []

    def test_load_corrupt_json(self, tmp_path):
        p = tmp_path / "history.json"
        p.write_text("not json!!!")
        with patch("apick.HISTORY_FILE", str(p)):
            assert apick.load_history() == []

    def test_load_non_list_json(self, tmp_path):
        p = tmp_path / "history.json"
        p.write_text('{"key": "value"}')
        with patch("apick.HISTORY_FILE", str(p)):
            assert apick.load_history() == []

    def test_save_and_load_roundtrip(self, tmp_path):
        hfile = str(tmp_path / ".apick" / "history.json")
        entries = [
            {"method": "GET", "url": "https://example.com/pets", "status_code": 200},
            {"method": "POST", "url": "https://example.com/pets", "status_code": 201},
        ]
        with patch("apick.HISTORY_FILE", hfile):
            apick.save_history(entries)
            loaded = apick.load_history()
        assert loaded == entries

    def test_truncation_to_max_history(self, tmp_path):
        hfile = str(tmp_path / ".apick" / "history.json")
        entries = [{"method": "GET", "url": f"https://example.com/{i}"} for i in range(600)]
        with patch("apick.HISTORY_FILE", hfile):
            apick.save_history(entries)
            loaded = apick.load_history()
        assert len(loaded) == apick.MAX_HISTORY
        # Should keep the last 500 (newest)
        assert loaded[0]["url"] == "https://example.com/100"
        assert loaded[-1]["url"] == "https://example.com/599"

    def test_format_history_newest_first(self):
        entries = [
            {
                "method": "GET",
                "url": "https://example.com/old",
                "timestamp": "2026-01-01T10:00:00",
                "status_code": 200,
                "summary": "Old",
            },
            {
                "method": "POST",
                "url": "https://example.com/new",
                "timestamp": "2026-02-01T10:00:00",
                "status_code": 201,
                "summary": "New",
            },
        ]
        output = apick.format_history_for_fzf(entries)
        lines = output.split("\n")
        assert len(lines) == 2
        # Newest (index 1) should appear first in display
        assert "example.com/new" in lines[0]
        assert "example.com/old" in lines[1]

    def test_format_history_colors(self):
        base = {"url": "https://a.com", "timestamp": "", "status_code": 200, "summary": ""}
        entries = [
            {"method": "GET", **base},
            {"method": "DELETE", **base},
        ]
        output = apick.format_history_for_fzf(entries)
        assert "\033[32m" in output  # GET = green
        assert "\033[31m" in output  # DELETE = red

    def test_format_history_null_status_shows_err(self):
        entries = [
            {"method": "GET", "url": "https://a.com", "timestamp": "",
             "status_code": None, "summary": ""},
        ]
        output = apick.format_history_for_fzf(entries)
        assert "err" in output

    def test_save_to_history_strips_authorization(self, tmp_path):
        hfile = str(tmp_path / ".apick" / "history.json")
        headers = {"Authorization": "Bearer secret", "Accept": "application/json"}
        with patch("apick.HISTORY_FILE", hfile):
            apick._save_to_history(
                "GET", "https://example.com/pets", headers, None, "spec.yaml", "List pets", 200
            )
            loaded = apick.load_history()
        assert len(loaded) == 1
        assert "Authorization" not in loaded[0]["headers"]
        assert loaded[0]["headers"]["Accept"] == "application/json"
        assert loaded[0]["status_code"] == 200


# ---------------------------------------------------------------------------
# execute_request
# ---------------------------------------------------------------------------


class TestExecuteRequest:
    def test_returns_status_code(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.reason_phrase = "OK"
        mock_resp.headers = {"content-type": "text/plain"}
        mock_resp.text = "ok"

        with patch("apick.httpx.request", return_value=mock_resp):
            result = apick.execute_request("GET", "https://example.com", {})
        assert result == 200
