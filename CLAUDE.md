# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Incalmo is an autonomous AI-driven network penetration testing framework that uses LLMs to conduct multi-stage attacks on networked systems. See arxiv:2501.16466 for the research paper. It supports two operation modes: LLM-guided attacks and deterministic state-machine attacks.

## Setup

Before running any commands, configure the environment:

```bash
# Copy and edit configuration files
cp config/config_example.json config/config.json
cp .env.example .env
# Then edit both files with your LLM API keys and settings
```

## Commands

### Python (uses `uv`)
```bash
uv sync                           # Install dependencies
uv run main.py                    # Run the strategy runner
uv run pytest                     # Run all tests
uv run pytest tests/test_file.py  # Run a specific test file
uv run pytest -k test_name        # Run tests matching a name pattern
uv run ruff format --check        # Lint check (CI gate)
uv run ruff format                # Auto-format code
```

### Frontend
```bash
cd incalmo/frontend/incalmo-ui
npm install
npm start        # Dev server on port 3000 (communicates with C2 server on port 8888)
npm run build
npm test
```

### Docker (Recommended for full environment)
```bash
cd docker
docker compose up                 # Start all containers (C2 server, targets, database)
docker compose exec attacker bash # Open shell in attacker container
# Then inside container: uv run main.py
```

## Architecture

Incalmo has two separate runtime processes that communicate over HTTP:

1. **C2 Server** (`incalmo/server.py`, port 8888) — Flask server that manages agents (sandcat.go implants) deployed on target hosts. Handles agent registration, command dispatch/polling, and environment state.

2. **Strategy Runner** (`main.py`) — reads config, initializes the state store, and runs the attack strategy loop. Communicates with the C2 server via `C2ApiClient`.

```
main.py → IncalmoRunner → Strategy → HighLevelActionOrchestrator
                                    → LowLevelActionOrchestrator → C2ApiClient → C2 Server (port 8888)
                                                                                      ↓
                                                                           sandcat.go agents on targets
```

### Strategy Layer (`incalmo/core/strategies/`)
- `StrategyRegistry` auto-registers subclasses via `__init_subclass__`; `StrategyFactory` instantiates from config.
- **LLM strategies**: `LangChainStrategy` drives `LangChainInterface` which maintains conversation history across supported LLM providers (OpenAI, Anthropic, Google, DeepSeek). The LLM emits structured Python code in XML tags (`<query>`, `<action>`, `<shell>`, `<finished>`) that are parsed and dispatched by `LLMStrategy`.
- **State-machine strategies**: Deterministic playbooks (`NetworkBFS`, `DarkSide`, `EquifaxTest`, `StrutsStrategy`, etc.) that don't require an LLM.

### Action Layer (`incalmo/core/actions/`)
- **High-level actions** — compound multi-step operations: `Scan`, `LateralMoveToHost`, `ExfiltrateData`, `FindInformationOnAHost`, `PrivilegeEscalation`, `AttackPathLateralMove`.
- **Low-level actions** — atomic shell commands sent to agents: `ScanNetwork`, `ScanHost`, `RunBashCommand`, `SSHLateralMove`, `ExploitStruts`, privilege escalation exploits, etc.
- **LLM agent actions** (`HighLevel/llm_agents/`) — sub-agent specializations where a separate LLM call handles a specific phase (scan, lateral move, priv esc, exfil, find info).

### State Management (`incalmo/core/services/`)
- `EnvironmentStateService` — maintains the live `Network` model (subnets, hosts, open ports, agents, credentials, critical data). Updated via `parse_events()` after each action.
- `AttackGraphService` — graph-based reasoning about viable attack paths.
- `IncalmoLogger` — structured logging to `output/`.

### LLM Prompting
System prompts live in `incalmo/core/strategies/llm/interfaces/preprompts/`. The `abstraction` field in config selects the prompt vocabulary:
- `incalmo` — full high-level SDK
- `low-level-actions` — atomic action vocabulary
- `agent_all` / `agent_scan` / `agent_lateral_move` / etc. — specialized sub-agent prompts
- `bash` — raw shell only

### C2 Server (`incalmo/c2server/`)
Flask blueprints: `agent_bp`, `command_bp`, `strategy_bp`, `logging_bp`, `file_bp`, `environment_bp`, `llm_bp`. State backed by SQLite; async task queue via Celery + SQLite broker.

### Configuration
`config/config_example.json` — specifies `strategy` (type + abstraction + model), `environment`, `c2c_server` URL, and `blacklist_ips`.

### Frontend (`incalmo/frontend/incalmo-ui/`)
React 19 + TypeScript SPA using ReactFlow for network topology visualization and MUI v7 for components. Runs on port 3000 and communicates with the C2 server (port 8888) via Axios for real-time attack monitoring and control.

## Testing

Tests live in `tests/`. The CI pipeline only runs `ruff format --check` — there is no automated test execution in CI. Run tests locally before committing:

```bash
uv run pytest                    # Run all tests
uv run pytest -v                 # Verbose output
uv run pytest tests/test_*.py -k keyword  # Run specific tests
```

## Strategy Development

Custom strategies can be LLM-based or deterministic state machines:

- **LLM strategies**: Subclass `LangChainStrategy` in `incalmo/core/strategies/llm/`. The LLM maintains conversation history and emits structured actions in XML tags (`<query>`, `<action>`, `<shell>`, `<finished>`).
- **State-machine strategies**: Subclass `IncalmoStrategy` in `incalmo/core/strategies/state_machine/` and implement the `async def step(self) -> bool:` method. See `NetworkBFS`, `DarkSide`, `StrutsStrategy` for examples.

Both are auto-registered via `StrategyRegistry` and instantiated by `StrategyFactory` from the `config.json` `strategy` field.

## Development Workflow

1. **Local development**: Run `uv sync`, edit code, lint with `ruff format`, test with `pytest`
2. **Full integration testing**: Use Docker Compose to spin up target environments, C2 server, and database
3. **Configuration**: Select your strategy type, LLM provider(s), and abstraction level in `config.json`
4. **Execution**: `uv run main.py` runs the strategy loop, which logs structured output to `output/`
5. **Monitoring**: Check logs in `output/` or use the React UI (port 3000) for real-time visibility
