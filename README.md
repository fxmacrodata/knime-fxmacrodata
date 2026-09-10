# FXMacroData for KNIME

Bring your FXMacroData subscription into KNIME workflows to compare covered currencies, analyse full available macroeconomic histories, and combine release calendars, FX rates and related datasets. Native tables connect directly to KNIME filtering, joining, charting and forecasting nodes.

**[Subscribe to FXMacroData](https://fxmacrodata.com/subscribe?utm_source=github&utm_medium=referral&utm_campaign=open_source_integrations&utm_content=knime_subscribe)** for access to covered non-USD datasets and full available history.

Evaluate the extension before subscribing with public USD catalogue, recent indicator history and release-calendar access, which require no API key or account.

[FXMacroData](https://fxmacrodata.com/?utm_source=github&utm_medium=referral&utm_campaign=open_source_integrations&utm_content=knime_readme) · [API documentation](https://fxmacrodata.com/documentation/reference?utm_source=github&utm_medium=referral&utm_campaign=open_source_integrations&utm_content=knime_docs) · [Complete node reference](OPERATIONS.md)

## Install

This extension targets **KNIME Analytics Platform 5.12**. Its source package includes a locked environment for Windows x64, Linux x64, macOS Intel and macOS Apple Silicon. KNIME's installer supplies the matching Python environment; data queries require internet access.

If you have the built `knime-fxmacrodata-0.1.0-update-site.zip`, extract it and use **File → Install KNIME Extensions → Available Software Sites → Add → Local** to select the extracted directory containing `content.jar`. Install **FXMacroData** and restart KNIME.

To build the same software update site from source, install [Pixi](https://pixi.sh/) and run these commands from the extracted source package:

```sh
pixi install -e build
pixi run -e build build ./release
```

In KNIME, choose **File → Install KNIME Extensions → Available Software Sites → Add → Local**, select `release/update-site` (the directory containing `content.jar`), then install **FXMacroData** and restart KNIME.

The package has 72 data/API tool nodes and an offline **FXMacroData Operations** discovery node under **Community → FXMacroData**. No notebook or Python Scripting node is needed to use them.

## Evaluate with public USD data

1. Add **Data Catalogue** from **FXMacroData → Data API**. Keep currency `USD` and credential `__public_usd__`, then execute it.
2. Inspect its **Records** output to choose an indicator from the catalogue.
3. Add **Indicator History**, set the same currency and indicator, and optionally include date, limit and offset parameters.
4. Connect Records to normal KNIME filtering, joining, grouping, chart or forecasting nodes. **Release Calendar** supplies the corresponding scheduled-release table.

Every REST operation and MCP tool has its own native dialog, including FX, reference rates, financial prices, rate curves/differentials, positioning, commodities, factors, risk sentiment, predictions, press releases, seasonality, visual artifacts and research tools. Use **FXMacroData Operations** to browse all names and their original schemas.

## Connect your subscription

To connect your subscription, create a **KNIME workflow credential** using KNIME's credentials configuration. Put your FXMacroData API key in its **password** field; its username is unused. Make that credential available to the node through KNIME's normal flow-variable connection and select its identifier in **KNIME credential**.

Only the identifier is saved in this extension's node settings. The password is resolved during execution and is not written to output tables, flow variables or node logs. `__public_usd__` explicitly disables authentication, including keys from the process environment. Do not paste keys into ordinary parameter fields or exported workflow text. Follow KNIME's credential-export controls when sharing workflows.

## Parameters and outputs

- Required parameters have native controls. Optional parameters have **Include** controls; unchecked parameters are omitted, preserving the API's defaults. Nullable parameters also provide an explicit **Send null** control.
- Structured inputs use a JSON editor with validation against the published schema. The original fields, terminology and distinctions between forecasts, observations and projections remain unchanged.
- **Records** contains native integer, number, boolean and string columns, with missing values preserved. Nested or mixed-type fields are JSON text. No inferred units, dates, fabricated observations or fallback datasets are added.
- **Complete response** retains the full original response JSON, source URL, documentation link, row count and each column's encoding. This output preserves nesting and metadata that do not fit a flat table.
- Results can have dataset-dependent columns, so KNIME learns the Records schema on execution. Visual-tool output retains artifact URLs and accompanying metadata; it does not download or execute remote HTML.
- Pagination remains explicit using each operation's page, offset, limit or cursor controls. **Stream Events** captures a finite number of events within a bounded time window; its response preserves capture status and reconnect cursors.
- Empty results produce an empty Records table and a warning. Authentication, throttling and service failures stop execution with an actionable error. They do not produce sample data.

## Development

```sh
pixi install -e test
pixi run -e test test
pixi run -e test lint
pixi run -e test python scripts/operation_matrix.py
```

Tests use KNIME's official Python testing backend and synthetic HTTP/MCP fixtures. They exercise native registration, dialog schemas, execution, typed data, credentials, errors and every packaged operation without an account. Desktop workflow execution is a separate validation surface.

`scripts/package.py` stages only explicitly listed integration files before invoking KNIME's native bundler. The source archive includes reproducible tests, a lockfile and the complete operation reference.

## License

The adapter is MIT licensed. Third-party dependencies retain their own licenses. This software license does not grant rights to redistribute API datasets or to the FXMacroData or KNIME trademarks. See [FXMacroData](https://fxmacrodata.com) for data access and licensing information.
