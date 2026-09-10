"""Synthetic transport fixtures exercise actual KNIME factories and tables."""
from copy import deepcopy
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import knime.extension as knext
import knime.extension.nodes as knodes
import knime.extension.parameter as kparam
import knime.extension.testing as ktest
import pandas as pd
import pytest
from fxmacrodata_public import list_operations

from src import extension
from src.extension import FXMacroDataClient
from src.tables import records_frame, result_frames


class Context(ktest.TestingExecutionContext):
    def __init__(self, secret="synthetic-knime-test-key"):
        super().__init__()
        self.secret = secret
        self.reads = []
        self.warnings = []
        self.progress = []

    def get_credential_names(self):
        return ["fxmd-test"]

    def get_credentials(self, name):
        self.reads.append(name)
        if name != "fxmd-test":
            raise KeyError("synthetic private credential diagnostic")
        return SimpleNamespace(password=self.secret)

    def get_input_specs(self):
        return []

    def set_warning(self, message):
        self.warnings.append(message)

    def set_progress(self, fraction, message=None):
        self.progress.append(fraction)


class Response:
    def __init__(self, payload, status=200, event_stream=False):
        self.status_code = status
        self.headers = {"Content-Type": "text/event-stream" if event_stream else "application/json"}
        self.content = ("data: " + json.dumps(payload) + "\n\n").encode() if event_stream else json.dumps(payload).encode()
        self.closed = False

    def iter_content(self, chunk_size):
        yield self.content

    def close(self):
        self.closed = True


class Session:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, deepcopy(kwargs)))
        body = kwargs.get("json") or {}
        if body.get("method") == "initialize":
            return Response({"jsonrpc": "2.0", "id": body["id"], "result": {"protocolVersion": "2025-03-26"}})
        if body.get("method") == "notifications/initialized":
            return Response(None, 202)
        if body.get("method") == "tools/call":
            return Response({"jsonrpc": "2.0", "id": body["id"], "result": self.payload}, self.status)
        return Response(self.payload, self.status, kwargs.get("headers", {}).get("Accept") == "text/event-stream")


def attach_transport(monkeypatch, payload, status=200):
    session = Session(payload, status)
    monkeypatch.setattr(extension, "FXMacroDataClient", lambda **kwargs: FXMacroDataClient(session=session, **kwargs))
    return session


def valid_node(operation):
    node = extension.NODE_FACTORIES[operation.name]()
    # Required fields are synthetic selectors, never economic observations.
    for name in operation.input_schema.get("required", []):
        attr = extension.PARAMETER_MAP[operation.name][name]["value"]
        if getattr(node, attr) == "":
            setattr(node, attr, {"indicator": "inflation", "factor": "monetary_stance", "currency": "USD",
                                 "base": "EUR", "quote": "USD", "positions_json": "[]"}.get(name, "fixture"))
    return node


def test_registry_matches_complete_client_inventory_and_has_native_ports():
    operations = list_operations()
    assert len(operations) == 72
    assert set(extension.NODE_FACTORIES) == {operation.name for operation in operations}
    assert len(extension.NODE_FACTORIES) == len(set(extension.NODE_FACTORIES))
    for operation in operations:
        registered = knodes._nodes[operation.name]
        assert registered.category == (extension.MCP_CATEGORY if operation.method == "MCP" else extension.REST_CATEGORY)
        assert len(registered.output_ports) == 2
        assert [port.name for port in registered.output_ports] == ["Records", "Complete response"]
        assert set(extension.PARAMETER_MAP[operation.name]) == set(operation.input_schema.get("properties", {}))


@pytest.mark.parametrize("operation", list_operations(), ids=lambda operation: operation.name)
def test_every_node_real_host_factory_dialog_schema_and_offline_configuration(operation):
    node = valid_node(operation)
    context = Context()
    schema = kparam.extract_schema(node, "0.1.0", context)
    ui = kparam.extract_ui_schema(node, context)
    saved = kparam.extract_parameters(node)
    assert schema and ui
    assert "synthetic-knime-test-key" not in json.dumps([schema, ui, saved])
    data_schema, response_schema = node.configure(context)
    assert data_schema is None
    assert "response_json" in response_schema.column_names
    assert context.reads == []
    args = node._arguments()
    assert set(operation.input_schema.get("required", [])).issubset(args)


@pytest.mark.parametrize("operation", list_operations(), ids=lambda operation: operation.name)
def test_every_native_node_executes_real_client_and_returns_typed_tables(operation, monkeypatch):
    payload = {"data": [{"fixture": "native-api-test", "val": None, "available": False, "count": 2,
                         "annotation": {"fixture_only": True}}], "metadata": {"units": "fixture"}}
    session = attach_transport(monkeypatch, payload)
    node = valid_node(operation)
    context = Context()
    records, complete = node.execute(context)
    assert isinstance(records, knext.Table) and isinstance(complete, knext.Table)
    metadata = complete.to_pandas().iloc[0]
    returned = json.loads(metadata["response_json"])
    assert returned == payload if operation.name != "stream_events" else returned["events"][0]["data"] == payload
    assert metadata["operation"] == operation.name
    for field, path, content in (("website_url", "/", "app"), ("documentation_url", "/documentation/reference", "docs")):
        link = urlsplit(metadata[field])
        assert link.scheme == "https" and link.hostname == "fxmacrodata.com" and link.path == path
        assert parse_qs(link.query) == {
            "utm_source": ["knime"], "utm_medium": ["integration"],
            "utm_campaign": ["open_source_integrations"], "utm_content": [content],
        }
    assert "utm_" not in metadata["source_url"]
    assert metadata["record_count"] == records.num_rows
    assert context.reads == []
    assert all("api_key" not in call[2]["params"] for call in session.calls)
    assert context.progress[-1] == 1.0
    if operation.method == "MCP":
        assert session.calls[-1][2]["json"]["params"]["name"] == operation.name.removeprefix("mcp_")
    elif operation.name != "stream_events":
        # KNIME's published testing backend does not implement pandas nullable
        # dtype -> schema mapping correctly. Assert the actual native table's
        # data instead; production Arrow conversion is checked separately.
        assert str(records.to_pandas()["count"].dtype) == "Int64"
        assert str(records.to_pandas()["available"].dtype) == "boolean"


def test_public_usd_defaults_and_inherited_environment_key_is_not_used(monkeypatch):
    monkeypatch.setenv("FXMD_API_KEY", "synthetic-ambient-key")
    monkeypatch.setenv("FXMACRODATA_API_KEY", "synthetic-ambient-key")
    session = attach_transport(monkeypatch, {"data": []})
    node = extension.NODE_FACTORIES["data_catalogue"]()
    assert node._arguments()["currency"] == "USD"
    node.execute(Context())
    assert session.calls[0][1].endswith("/USD")
    assert "api_key" not in session.calls[0][2]["params"]


def test_selected_native_credential_is_resolved_at_execution_and_not_saved(monkeypatch):
    session = attach_transport(monkeypatch, {"data": [{"echo": "synthetic-knime-test-key"}]})
    node = extension.NODE_FACTORIES["data_catalogue"]()
    node.credential = "fxmd-test"
    context = Context()
    node.configure(context)
    assert context.reads == []
    rows, complete = node.execute(context)
    assert context.reads == ["fxmd-test"]
    assert session.calls[0][2]["params"]["api_key"] == context.secret
    assert context.secret not in json.dumps(kparam.extract_parameters(node))
    assert context.secret not in complete.to_pandas().to_json()
    assert context.secret not in rows.to_pandas().to_json()


def test_native_credential_failure_is_safe(monkeypatch):
    session = attach_transport(monkeypatch, {})
    node = extension.NODE_FACTORIES["ping"]()
    node.credential = "missing"
    with pytest.raises(knext.InvalidParametersError) as error:
        node.execute(Context())
    assert "synthetic private" not in str(error.value)
    assert session.calls == []


@pytest.mark.parametrize("status", [301, 401, 403, 404, 429, 500])
def test_errors_do_not_become_fake_data_or_expose_body(status, monkeypatch):
    attach_transport(monkeypatch, {"error": "synthetic-sensitive-detail"}, status)
    with pytest.raises(RuntimeError) as error:
        extension.NODE_FACTORIES["ping"]().execute(Context())
    assert "synthetic-sensitive-detail" not in str(error.value)


def test_optional_pagination_and_nullable_parameters_preserve_exact_arguments(monkeypatch):
    session = attach_transport(monkeypatch, {"data": []})
    node = extension.NODE_FACTORIES["indicator_history"]()
    node.arg_indicator = "inflation"
    node.include_offset = True
    node.arg_offset = 20
    node.include_limit = True
    node.arg_limit = 10
    node.include_page = True
    node.null_page = True
    assert node._arguments()["page"] is None
    node.execute(Context())
    params = session.calls[0][2]["params"]
    assert params["offset"] == 20 and params["limit"] == 10
    assert "page" not in params
    assert "start_date" not in params


def test_zero_results_are_empty_with_original_response_and_warning(monkeypatch):
    payload = {"data": [], "availability": "unavailable", "reason": "fixture"}
    attach_transport(monkeypatch, payload)
    context = Context()
    records, complete = extension.NODE_FACTORIES["ping"]().execute(context)
    assert records.num_rows == 0
    assert complete.to_pandas().iloc[0]["status"] == "empty"
    assert json.loads(complete.to_pandas().iloc[0]["response_json"]) == payload
    assert len(context.warnings) == 1


def test_operation_catalogue_has_all_schemas_and_matches_configure():
    node = extension.OperationCatalogue()
    context = Context()
    table = node.execute(context)
    assert set(table.to_pandas()["operation"]) == set(extension.NODE_FACTORIES)
    assert list(table.to_pandas().columns) == list(node.configure(context).column_names)
    assert table.to_pandas()["website_url"].nunique() == 1
    assert table.to_pandas()["documentation_url"].nunique() == 1
    for field in ("website_url", "documentation_url"):
        query = parse_qs(urlsplit(table.to_pandas()[field].iloc[0]).query)
        assert query["utm_source"] == ["knime"] and query["utm_medium"] == ["integration"]
        assert query["utm_campaign"] == ["open_source_integrations"]
    assert context.reads == []


def test_registered_node_and_category_backlinks_have_runtime_attribution():
    catalogue = extension.OperationCatalogue()
    descriptions = [catalogue.__doc__, *[factory().__doc__ for factory in extension.NODE_FACTORIES.values()]]
    category = next(item.to_dict() for item in knodes._categories if item.to_dict()["level_id"] == "fxmacrodata")
    descriptions.append(category["description"])
    for description in descriptions:
        assert "https://fxmacrodata.com/?utm_source=knime&utm_medium=integration" in description
        assert "utm_campaign=open_source_integrations&utm_content=app" in description


def test_table_projection_preserves_types_missing_values_nested_json_and_large_integers():
    source = [{"i": 2, "f": 0.5, "b": True, "s": "2.0", "nested": {"v": [1, None]}, "large": 2**65},
              {"i": None, "f": None, "b": None, "s": None, "nested": None, "large": 1}]
    original = deepcopy(source)
    frame, encodings = records_frame(source)
    assert source == original
    assert str(frame["i"].dtype) == "Int64" and str(frame["f"].dtype) == "Float64"
    assert str(frame["b"].dtype) == "boolean" and frame["s"].iloc[0] == "2.0"
    assert pd.isna(frame["i"].iloc[1])
    assert json.loads(frame["nested"].iloc[0]) == {"v": [1, None]}
    assert json.loads(frame["large"].iloc[0]) == 2**65
    assert encodings["nested"] == encodings["large"] == "json"


def test_cancellation_prevents_request(monkeypatch):
    session = attach_transport(monkeypatch, {})
    context = Context()
    context.is_canceled = lambda: True
    with pytest.raises(RuntimeError, match="canceled"):
        extension.NODE_FACTORIES["ping"]().execute(context)
    assert session.calls == []


def test_visual_artifact_links_and_structured_content_are_retained():
    from fxmacrodata_public import Result
    payload = {"structuredContent": {"artifact_url": "https://fxmacrodata.com/fixture-artifact", "summary": "fixture"},
               "content": [{"type": "text", "text": "fixture"}], "isError": False}
    rows, complete = result_frames(Result("mcp_plot_visual_artifact", payload))
    assert rows["artifact_url"].iloc[0] == payload["structuredContent"]["artifact_url"]
    assert json.loads(complete["response_json"].iloc[0]) == payload


def test_cancellation_after_request_preserves_canceled_status(monkeypatch):
    session = attach_transport(monkeypatch, {"data": [{"fixture": "canceled-result"}]})
    context = Context()
    context.is_canceled = lambda: bool(session.calls)
    with pytest.raises(RuntimeError, match="execution canceled"):
        extension.NODE_FACTORIES["ping"]().execute(context)
    assert context.progress == [0.1]


@pytest.mark.parametrize("secret_field_value", [True, False, None, 17])
def test_escaped_json_credential_is_redacted_before_native_tables(monkeypatch, secret_field_value):
    secret = "synthetic-knime-escaped-key"
    encoded = "".join("\\u%04x" % ord(char) for char in secret)
    nested = '{"note":"' + encoded + '","apiKey":' + json.dumps(secret_field_value) + ',"public_value":1,"available":false}'
    attach_transport(monkeypatch, {"content": [{"type": "text", "text": nested}], "isError": False})
    node = extension.NODE_FACTORIES["mcp_ping"]()
    node.credential = "fxmd-test"
    records, complete = node.execute(Context(secret))
    rows = records.to_pandas()
    assert rows["public_value"].iloc[0] == 1
    assert not rows["available"].iloc[0]
    assert rows["note"].iloc[0] == "[redacted]"
    assert rows["apiKey"].iloc[0] == "[redacted]"
    assert secret not in rows.to_json() + complete.to_pandas().to_json()
    payload = json.loads(complete.to_pandas()["response_json"].iloc[0])
    assert payload["isError"] is False
    assert json.loads(payload["content"][0]["text"])["note"] == "[redacted]"


@pytest.mark.parametrize("encoding", ["json", "unicode_lower", "unicode_upper"])
def test_configured_credential_escapes_in_plain_prose_are_redacted(monkeypatch, encoding):
    secret = 'synthetic-knime-"key"\\é😀'
    raw = secret.encode("utf-16-be")
    escaped = json.dumps(secret, ensure_ascii=True)[1:-1] if encoding == "json" else "".join(
        "\\u" + (raw[index:index + 2].hex().upper() if encoding == "unicode_upper" else raw[index:index + 2].hex())
        for index in range(0, len(raw), 2)
    )
    attach_transport(monkeypatch, {"data": [{"note": "Echo " + escaped + ".", "available": False}]})
    node = extension.NODE_FACTORIES["ping"]()
    node.credential = "fxmd-test"
    records, complete = node.execute(Context(secret))
    assert records.to_pandas()["note"].iloc[0] == "Echo [redacted]."
    payload = json.loads(complete.to_pandas()["response_json"].iloc[0])
    assert payload["data"][0] == {"note": "Echo [redacted].", "available": False}
