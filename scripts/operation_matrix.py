"""Regenerate the public operation-to-node reference from the pinned client."""
from pathlib import Path
from fxmacrodata_public import list_operations

root = Path(__file__).resolve().parents[1]
operations = list_operations()
lines = [
    "# FXMacroData operation coverage", "",
    "Every operation below is a native KNIME source node with its own configuration dialog, Records table and Complete response table. Search its node name under Community → FXMacroData. No operation is hidden behind example code.", "",
    "Primitive inputs use native text, choice, integer, number and boolean controls. Optional inputs have Include controls; nullable inputs also have explicit null controls. Structured values use a JSON editor and the original input schema for validation. Credentials are a separate KNIME credential selector.", "",
    "The complete response preserves the API's original fields and nesting. Records use typed scalar columns; nested or heterogeneous columns retain JSON text. Schema is determined when the node executes. Empty data remains an empty table. Pagination controls and the finite stream event/time limits preserve the public client contract.", "",
    f"Inventory: {len(operations)} operations ({sum(op.method == 'GET' for op in operations)} REST, {sum(op.method == 'MCP' for op in operations)} MCP), plus the offline FXMacroData Operations discovery node.", "",
    "[FXMacroData](https://fxmacrodata.com) · [API reference](https://fxmacrodata.com/documentation/reference) · [MCP documentation](https://fxmacrodata.com/documentation/mcp-server)", "",
    "| Operation / stable node ID | Native node name | Protocol | Inputs (required marked *) |",
    "| --- | --- | --- | --- |",
]
for op in operations:
    required = set(op.input_schema.get("required", []))
    fields = ", ".join("`" + name + "`" + ("*" if name in required else "") for name in op.input_schema.get("properties", {})) or "None"
    name = op.name.removeprefix("mcp_").replace("_", " ").title() + (" (MCP)" if op.method == "MCP" else "")
    lines.append(f"| `{op.name}` | {name} | {op.method} | {fields} |")
(root / "OPERATIONS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
