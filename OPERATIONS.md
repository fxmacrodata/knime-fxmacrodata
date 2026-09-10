# FXMacroData operation coverage

Every operation below is a native KNIME source node with its own configuration dialog, Records table and Complete response table. Search its node name under Community → FXMacroData. No operation is hidden behind example code.

Primitive inputs use native text, choice, integer, number and boolean controls. Optional inputs have Include controls; nullable inputs also have explicit null controls. Structured values use a JSON editor and the original input schema for validation. Credentials are a separate KNIME credential selector.

The complete response preserves the API's original fields and nesting. Records use typed scalar columns; nested or heterogeneous columns retain JSON text. Schema is determined when the node executes. Empty data remains an empty table. Pagination controls and the finite stream event/time limits preserve the public client contract.

Inventory: 72 operations (23 REST, 49 MCP), plus the offline FXMacroData Operations discovery node.

[FXMacroData](https://fxmacrodata.com) · [API reference](https://fxmacrodata.com/documentation/reference) · [MCP documentation](https://fxmacrodata.com/documentation/mcp-server)

| Operation / stable node ID | Native node name | Protocol | Inputs (required marked *) |
| --- | --- | --- | --- |
| `health` | Health | GET | None |
| `ping` | Ping | GET | None |
| `forex` | Forex | GET | `base`*, `quote`*, `start_date`, `end_date`, `limit`, `offset`, `page`, `indicators` |
| `intraday_reference_rates` | Intraday Reference Rates | GET | `base`*, `quote`*, `start_time`, `end_time` |
| `fx_sources` | Fx Sources | GET | None |
| `fx_source_universe` | Fx Source Universe | GET | `currency`, `source` |
| `data_catalogue` | Data Catalogue | GET | `currency`*, `include_capabilities`, `include_coverage`, `indicator` |
| `release_calendar` | Release Calendar | GET | `currency`*, `indicator`, `start_date`, `end_date`, `timezone` |
| `market_sessions` | Market Sessions | GET | `at` |
| `rate_differentials` | Rate Differentials | GET | `base`*, `quote`*, `measure`, `rate_type`, `curve_family`, `start_tenor_years`, `end_tenor_years`, `start_date`, `end_date`, `limit`, `offset` |
| `curves` | Curves | GET | `currency`*, `curve_family`, `metric`, `view`, `method`, `date` |
| `financial_prices` | Financial Prices | GET | `currency`*, `source`, `start_date`, `end_date`, `measure`, `instrument_id`, `issuer`, `limit`, `offset` |
| `press_releases` | Press Releases | GET | `currency`*, `limit`, `offset` |
| `risk_sentiment` | Risk Sentiment | GET | `start_date`, `end_date`, `limit`, `offset` |
| `factors` | Factors | GET | `currency`*, `factor`*, `start_date`, `end_date`, `include_components`, `include_sources`, `limit`, `offset` |
| `event_predictions` | Event Predictions | GET | `currency`*, `indicator`*, `prediction_class`, `prediction_type`, `prediction_source`, `official_limit`, `pre_release_only`, `seasonality`, `frequency`, `annualization`, `period_aggregation`, `basis`, `start_date`, `end_date`, `limit`, `offset`, `page`, `before_date` |
| `latest_announcements` | Latest Announcements | GET | `currency`* |
| `indicator_history` | Indicator History | GET | `currency`*, `indicator`*, `start_date`, `end_date`, `series_mode`, `limit`, `offset`, `page`, `seasonality`, `frequency`, `annualization`, `period_aggregation`, `revisions`, `basis`, `official_only` |
| `cot` | Cot | GET | `currency`*, `start_date`, `end_date`, `limit`, `offset`, `page` |
| `latest_commodities` | Latest Commodities | GET | None |
| `commodities` | Commodities | GET | `indicator`*, `start_date`, `end_date`, `limit`, `offset`, `page` |
| `announcement_changes` | Announcement Changes | GET | `currencies`, `indicators`, `since`, `limit`, `payload` |
| `stream_events` | Stream Events | GET | `currencies`, `indicators`, `payload`, `live_only`, `max_age_ms`, `Last-Event-ID`, `max_events`, `max_seconds` |
| `mcp_ping` | Ping (MCP) | MCP | None |
| `mcp_mcp_capabilities` | Mcp Capabilities (MCP) | MCP | None |
| `mcp_mcp_auth_guide` | Mcp Auth Guide (MCP) | MCP | None |
| `mcp_subscribe_for_mcp_access` | Subscribe For Mcp Access (MCP) | MCP | None |
| `mcp_data_catalogue` | Data Catalogue (MCP) | MCP | `currency`*, `include_coverage`, `include_capabilities`, `indicator` |
| `mcp_risk_sentiment` | Risk Sentiment (MCP) | MCP | `start_date`, `end_date` |
| `mcp_macro_news` | Macro News (MCP) | MCP | `currency`*, `lookback_days`, `limit`, `offset` |
| `mcp_release_calendar` | Release Calendar (MCP) | MCP | `currency`*, `indicator`, `start_date`, `end_date`, `timezone` |
| `mcp_release_calendar_visual_artifact` | Release Calendar Visual Artifact (MCP) | MCP | `currency`*, `indicator`, `start_date`, `end_date`, `timezone` |
| `mcp_event_predictions` | Event Predictions (MCP) | MCP | `currency`*, `indicator`*, `prediction_type`, `prediction_source`, `start_date`, `end_date`, `limit`, `offset`, `page` |
| `mcp_latest_announcements` | Latest Announcements (MCP) | MCP | `currency`* |
| `mcp_announcement_changes` | Announcement Changes (MCP) | MCP | `currencies`, `indicators`, `since`, `limit`, `payload` |
| `mcp_press_releases` | Press Releases (MCP) | MCP | `currency`*, `limit`, `offset` |
| `mcp_macro_factor` | Macro Factor (MCP) | MCP | `currency`*, `factor`*, `start_date`, `end_date`, `include_components`, `include_sources`, `limit`, `offset` |
| `mcp_fx_reference_sources` | Fx Reference Sources (MCP) | MCP | None |
| `mcp_fx_reference_universe` | Fx Reference Universe (MCP) | MCP | `currency`, `source` |
| `mcp_fx_intraday_reference_rates` | Fx Intraday Reference Rates (MCP) | MCP | `base`*, `quote`*, `start_time`, `end_time` |
| `mcp_rate_curve` | Rate Curve (MCP) | MCP | `currency`*, `curve_family`, `metric`, `view`, `method`, `date` |
| `mcp_rate_differentials` | Rate Differentials (MCP) | MCP | `base`*, `quote`*, `measure`, `rate_type`, `curve_family`, `start_tenor_years`, `end_tenor_years`, `start_date`, `end_date`, `limit`, `offset` |
| `mcp_latest_commodities` | Latest Commodities (MCP) | MCP | None |
| `mcp_forex` | Forex (MCP) | MCP | `base`*, `quote`*, `start_date`, `end_date`, `indicators` |
| `mcp_seasonality` | Seasonality (MCP) | MCP | `instrument`*, `lookback_years`, `month`, `end_date` |
| `mcp_indicator_query` | Indicator Query (MCP) | MCP | `currency`, `indicator`, `start_date`, `end_date`, `limit`, `offset`, `page`, `slug`, `official_only` |
| `mcp_plot_visual_artifact` | Plot Visual Artifact (MCP) | MCP | `query`, `series`, `source`, `currency`, `indicator`, `base`, `quote`, `prediction_type`, `prediction_source`, `x_axis`, `y_key`, `y_label`, `title`, `chart_kind`, `start_date`, `end_date`, `limit`, `offset`, `page` |
| `mcp_indicator_visual_artifact` | Indicator Visual Artifact (MCP) | MCP | `currency`*, `indicator`*, `start_date`, `end_date`, `limit`, `offset`, `page` |
| `mcp_forex_visual_artifact` | Forex Visual Artifact (MCP) | MCP | `base`*, `quote`*, `start_date`, `end_date`, `indicators` |
| `mcp_commodities_visual_artifact` | Commodities Visual Artifact (MCP) | MCP | `indicator`*, `start_date`, `end_date` |
| `mcp_cot_visual_artifact` | Cot Visual Artifact (MCP) | MCP | `currency`*, `start_date`, `end_date`, `metric` |
| `mcp_policy_rate_differential_visual_artifact` | Policy Rate Differential Visual Artifact (MCP) | MCP | `base`*, `quote`*, `start_date`, `end_date` |
| `mcp_macro_briefing_task` | Macro Briefing Task (MCP) | MCP | `currency`* |
| `mcp_indicator_intel_task` | Indicator Intel Task (MCP) | MCP | `currency`*, `indicator`*, `start_date`, `end_date` |
| `mcp_pair_intel_task` | Pair Intel Task (MCP) | MCP | `base`*, `quote`*, `start_date`, `end_date` |
| `mcp_macro_heatmap_task` | Macro Heatmap Task (MCP) | MCP | `currencies`, `indicators`, `start_date`, `end_date` |
| `mcp_policy_scenario_modeler_task` | Policy Scenario Modeler Task (MCP) | MCP | `base`*, `quote`*, `shock_leg`, `shock_bps`, `policy_shock_bps`, `elasticity_per_100bps`, `start_date`, `end_date` |
| `mcp_macro_war_room_task` | Macro War Room Task (MCP) | MCP | `base`, `quote`, `currency`, `indicator`, `start_date`, `end_date` |
| `mcp_event_impact_replay_task` | Event Impact Replay Task (MCP) | MCP | `currency`*, `indicator`*, `base`, `quote`, `lookback_events`, `start_date`, `end_date` |
| `mcp_quant_scenario_lab_task` | Quant Scenario Lab Task (MCP) | MCP | `base`*, `quote`*, `shock_leg`, `shock_bps`, `elasticity_per_100bps`, `annualized_volatility_pct`, `horizon_days`, `start_date`, `end_date` |
| `mcp_known_at_time_task` | Known At Time Task (MCP) | MCP | `currency`*, `indicator`*, `as_of`*, `start_date`, `end_date` |
| `mcp_macro_regime_classifier_task` | Macro Regime Classifier Task (MCP) | MCP | `currency`*, `start_date`, `end_date` |
| `mcp_release_risk_score_task` | Release Risk Score Task (MCP) | MCP | `base`*, `quote`*, `horizon_events` |
| `mcp_portfolio_risk_engine_task` | Portfolio Risk Engine Task (MCP) | MCP | `positions_json`*, `stress_shock_pct`, `horizon_events` |
| `mcp_fx_trade_setup_task` | Fx Trade Setup Task (MCP) | MCP | `base`*, `quote`*, `horizon_events`, `include_cot` |
| `mcp_fx_backtest_task` | Fx Backtest Task (MCP) | MCP | `base`*, `quote`*, `start_date`, `end_date`, `strategy`, `momentum_lookback`, `transaction_cost_bps`, `initial_capital`, `event_gated`, `event_window_days` |
| `mcp_macro_research_pack_task` | Macro Research Pack Task (MCP) | MCP | `currency`*, `indicator`*, `base`, `quote`, `start_date`, `end_date` |
| `mcp_market_sessions` | Market Sessions (MCP) | MCP | `at` |
| `mcp_cot_data` | Cot Data (MCP) | MCP | `currency`*, `start_date`, `end_date` |
| `mcp_commodities` | Commodities (MCP) | MCP | `indicator`, `symbol`, `start_date`, `end_date` |
| `mcp_financial_prices` | Financial Prices (MCP) | MCP | `currency`*, `source`, `start_date`, `end_date`, `measure`, `instrument_id`, `issuer`, `limit`, `offset` |
| `mcp_official_dataset_family` | Official Dataset Family (MCP) | MCP | `endpoint_type`*, `dataset`*, `currency`*, `component` |
