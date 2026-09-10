"""Native KNIME nodes generated from the published FXMacroData operation contract."""
from __future__ import annotations

from copy import deepcopy
import json
import re

import jsonschema
import knime.extension as knext
import pandas as pd
from fxmacrodata_public import FXMacroDataClient as _PublicClient
from fxmacrodata_public import FXMacroDataError, Result, list_operations
from fxmacrodata_public.client import SCHEMA_REGISTRY

from tables import DOCUMENTATION, WEBSITE, json_text, result_frames
from response_safety import sanitize_response

PUBLIC_ACCESS = "__public_usd__"
OPERATIONS = list_operations()
NODE_FACTORIES = {}
PARAMETER_MAP = {}
ICON = "icons/fxmacrodata.png"


class FXMacroDataClient(_PublicClient):
    def _safe(self, value):
        # Parse nested JSON before any text redaction can invalidate it.
        return sanitize_response(value, self._api_key)


CATEGORY = knext.category(
    path="/community", level_id="fxmacrodata", name="FXMacroData",
    description=f"Macroeconomic indicators, releases and market data. {WEBSITE}",
    icon="icons/fxmacrodata-category.png",
)
REST_CATEGORY = knext.category(
    CATEGORY, "rest", "Data API", "FXMacroData public data API operations", "icons/fxmacrodata-category.png",
)
MCP_CATEGORY = knext.category(
    CATEGORY, "mcp", "MCP Tools", "FXMacroData MCP data, research and visual tools", "icons/fxmacrodata-category.png",
)


def credential_choices(context):
    # The saved setting contains a credential identifier, never its password.
    return [PUBLIC_ACCESS, *[name for name in context.get_credential_names() if name != PUBLIC_ACCESS]]


def _simple_schema(schema):
    if "anyOf" in schema:
        choices = [part for part in schema["anyOf"] if part.get("type") != "null"]
        if len(choices) == 1:
            return {**schema, **choices[0]}
    return schema


def _nullable(schema):
    return schema.get("type") == "null" or "null" in (
        schema.get("type") if isinstance(schema.get("type"), list) else []
    ) or any(part.get("type") == "null" for part in schema.get("anyOf", []))


def _default(name, schema):
    if name == "currency":
        return "USD"
    if schema.get("default") is not None:
        return deepcopy(schema["default"])
    values = schema.get("enum") or schema.get("examples") or []
    if values:
        return deepcopy(values[0])
    if "example" in schema:
        return deepcopy(schema["example"])
    kind = schema.get("type")
    if kind == "boolean":
        return False
    if kind in ("integer", "number"):
        return max(0, schema.get("minimum", 0))
    if kind == "array":
        return []
    if kind == "object":
        return {}
    return ""


def _parameter(name, schema):
    simple = _simple_schema(schema)
    kind = simple.get("type")
    label = name.replace("_", " ").replace("-", " ").capitalize()
    description = schema.get("description", "FXMacroData parameter: " + name)
    default = _default(name, simple)
    if kind == "boolean":
        return knext.BoolParameter(label, description, bool(default)), False
    if kind in ("integer", "number"):
        factory = knext.IntParameter if kind == "integer" else knext.DoubleParameter
        return factory(label, description, default, min_value=simple.get("minimum"), max_value=simple.get("maximum")), False
    if kind == "string":
        enum = simple.get("enum")
        if enum and all(isinstance(item, str) for item in enum):
            return knext.StringParameter(label, description, str(default), enum=enum), False
        return knext.StringParameter(label, description, str(default)), False
    return knext.MultilineStringParameter(
        label + " (JSON)", description + "\nEnter a JSON value matching the documented schema.",
        json_text(default),
    ), True


def _response_schema():
    return knext.Schema.from_columns([
        knext.Column(knext.string(), name) if name != "record_count" else knext.Column(knext.int64(), name)
        for name in ("operation", "source_url", "website_url", "documentation_url", "record_count",
                     "status", "column_encodings_json", "response_json")
    ])


class _OperationNode:
    def _arguments(self):
        arguments = {}
        for name, attributes in PARAMETER_MAP[self.operation.name].items():
            if attributes["include"] and not getattr(self, attributes["include"]):
                continue
            if attributes["null"] and getattr(self, attributes["null"]):
                arguments[name] = None
                continue
            value = getattr(self, attributes["value"])
            if attributes["json"]:
                try:
                    value = json.loads(value)
                except (ValueError, TypeError):
                    raise knext.InvalidParametersError("A JSON parameter is invalid. Check its documented schema.") from None
            arguments[name] = value
        try:
            jsonschema.Draft202012Validator(self.operation.input_schema, registry=SCHEMA_REGISTRY).validate(arguments)
        except (jsonschema.ValidationError, jsonschema.SchemaError):
            raise knext.InvalidParametersError("Check required parameters and allowed values for this operation.") from None
        return arguments

    def configure(self, context):
        self._arguments()
        # Result columns depend on the chosen published dataset; configure never
        # performs a request or resolves a password to guess the output schema.
        return None, _response_schema()

    def execute(self, context):
        if context.is_canceled():
            raise RuntimeError("FXMacroData execution canceled.")
        arguments = self._arguments()
        key = ""  # Explicitly disable ambient environment-key discovery.
        if self.credential != PUBLIC_ACCESS:
            try:
                key = context.get_credentials(self.credential).password
            except Exception:
                raise knext.InvalidParametersError("Select an available KNIME credential containing the API key in its password field.") from None
            if not isinstance(key, str) or not key.strip():
                raise knext.InvalidParametersError("The selected KNIME credential has an empty API-key password.")
        context.set_progress(0.1, "Requesting FXMacroData")
        try:
            with FXMacroDataClient(api_key=key, timeout=self.timeout) as client:
                result = client.execute(self.operation.name, arguments)
            result = Result(result.operation, sanitize_response(result.payload, key), result.source_url)
            frames = result_frames(result)
            if context.is_canceled():
                raise RuntimeError("FXMacroData execution canceled.")
            outputs = tuple(knext.Table.from_pandas(frame) for frame in frames)
        except FXMacroDataError as error:
            raise RuntimeError(str(error)) from None
        except Exception:
            if context.is_canceled():
                raise RuntimeError("FXMacroData execution canceled.") from None
            raise RuntimeError("FXMacroData could not produce a table. Check dataset availability and parameter values.") from None
        finally:
            key = ""
        if frames[0].empty:
            context.set_warning("FXMacroData returned no records for this query. The response table retains its availability metadata.")
        context.set_progress(1.0, "FXMacroData tables ready")
        return outputs


def _register_operation(operation):
    attrs = {
        "__module__": __name__, "operation": operation,
        "__doc__": operation.description + "\n\n"
        + "Returns native KNIME columns and a separate complete response table. "
        + "Public USD catalogue, history and release calendars need no credential. "
        + "For optional protected datasets, select a KNIME workflow credential whose password contains your API key. "
        + "The credential identifier is saved; its password is resolved only during execution.\n\n"
        + f"[FXMacroData]({WEBSITE}) · [API documentation]({DOCUMENTATION})\n\n"
        + f"Operation: `{operation.name}`. Source: `{operation.method} {operation.path}`. "
        + "Use the Include controls to send optional parameters; unchecked values are omitted. "
        + "Pagination remains explicit through the endpoint's page, offset or cursor parameters. "
        + "Stream events use a finite event/time capture, rather than a continuously executing workflow.",
        "credential": knext.StringParameter(
            "KNIME credential", "Choose __public_usd__ for no-key access. Otherwise select a workflow credential with the API key as its password; the username is unused.",
            PUBLIC_ACCESS, choices=credential_choices,
        ),
        "timeout": knext.IntParameter("Request timeout (seconds)", "Maximum request timeout. Event streams also use their configured finite capture budget.", 30, min_value=1, max_value=120),
    }
    mapping = {}
    required = set(operation.input_schema.get("required", []))
    for name, schema in operation.input_schema.get("properties", {}).items():
        suffix = re.sub(r"\W", "_", name)
        value_attr = "arg_" + suffix
        include_attr = None if name in required else "include_" + suffix
        null_attr = "null_" + suffix if _nullable(schema) else None
        parameter, is_json = _parameter(name, schema)
        if include_attr:
            attrs[include_attr] = knext.BoolParameter(
                "Include " + name, "Send this optional argument. Unchecked leaves the API default unchanged.", name == "currency",
            )
            parameter.rule(knext.OneOf(attrs[include_attr], [True]), knext.Effect.SHOW)
        attrs[value_attr] = parameter
        if null_attr:
            attrs[null_attr] = knext.BoolParameter("Send null for " + name, "Send JSON null instead of the value above when this parameter is included.", False, is_advanced=True)
        mapping[name] = {"value": value_attr, "include": include_attr, "null": null_attr, "json": is_json}
    PARAMETER_MAP[operation.name] = mapping
    node_class = type("FXMacroData_" + operation.name, (_OperationNode,), attrs)
    node_class = knext.output_table("Complete response", "Original response JSON, source links, row count and column encodings.")(node_class)
    node_class = knext.output_table("Records", "Dataset rows as typed KNIME columns. Nested or mixed fields are JSON text; missing data stays missing.")(node_class)
    name = operation.name.removeprefix("mcp_").replace("_", " ").title()
    factory = knext.node(
        name=name + (" (MCP)" if operation.method == "MCP" else ""),
        node_type=knext.NodeType.SOURCE, icon_path=ICON,
        category=MCP_CATEGORY if operation.method == "MCP" else REST_CATEGORY,
        id=operation.name, keywords=["FXMacroData", "macro", "finance", operation.name],
    )(node_class)
    NODE_FACTORIES[operation.name] = factory
    globals()[node_class.__name__] = factory


for _operation in OPERATIONS:
    _register_operation(_operation)


@knext.node("FXMacroData Operations", knext.NodeType.SOURCE, ICON, CATEGORY, id="operation_catalogue")
@knext.output_table("Operations", "Every packaged REST operation and MCP tool, with its schema and matching KNIME node identifier.")
class OperationCatalogue:
    """Discover available FXMacroData nodes without a network request.

    Filter the table by operation, protocol or description to find a node, then
    search its name in KNIME's node repository. Each operation has its own native
    configuration dialog. [FXMacroData](https://fxmacrodata.com/?utm_source=knime&utm_medium=integration&utm_campaign=open_source_integrations&utm_content=app) provides public
    USD catalogue, history and release-calendar access without an API key.
    """

    def configure(self, context):
        return knext.Schema.from_columns([knext.Column(knext.string(), name) for name in (
            "operation", "node_name", "protocol", "description", "path", "input_schema_json", "website_url", "documentation_url")])

    def execute(self, context):
        rows = [{
            "operation": operation.name,
            "node_name": operation.name.removeprefix("mcp_").replace("_", " ").title() + (" (MCP)" if operation.method == "MCP" else ""),
            "protocol": operation.method,
            "description": operation.description,
            "path": operation.path,
            "input_schema_json": json_text(operation.input_schema),
            "website_url": WEBSITE,
            "documentation_url": DOCUMENTATION,
        } for operation in OPERATIONS]
        return knext.Table.from_pandas(pd.DataFrame(rows, dtype="string"))
