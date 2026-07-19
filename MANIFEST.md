# Manifest

File installati alla radice del repository:

- `AGENTS.md`
- `.codex/config.toml`
- `.codex/agents/scanner.toml`
- `.codex/agents/implementer.toml`
- `.codex/agents/test-reviewer.toml`
- `.codex/agents/docs-reviewer.toml`
- `.agents/skills/memoria-session/SKILL.md`
- `.agents/skills/memoria-planner/SKILL.md`
- `.agents/skills/memoria-roadmap-selector/SKILL.md`
- `.agents/skills/memoria-quality-gate/SKILL.md`
- `.agents/skills/memoria-source-registry/SKILL.md`
- `.agents/skills/memoria-profile-feedback/SKILL.md`

La patch è idempotente e crea un backup timestampato dei soli file eventualmente
sovrascritti. Non interviene sul planner persistente.
