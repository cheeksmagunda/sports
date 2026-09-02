@AGENTS.md

## Claude Code

The portfolio contract above is canonical. Child `AGENTS.md` files add
application rules and exact commands; a matching `CLAUDE.md` in each
application directory imports them on demand.

- Python monorepo driven by `uv`. Use `uv run` rather than a bare `python3`.
- Dependency direction is one way: sport application to `oracle-core`, never back.
- Check `STATUS.md` in the target application before acting on it.
