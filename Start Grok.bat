@echo off
REM New Grok session for Dodgeville PD — token-minimized startup
cd /d "%~dp0"
python dev.py agent-pack -q
python dev.py context-window task "Grok session — Dodgeville PD Scheduler"
grok --cwd "%CD%" "New session. Read logs/agent_pack/latest.md and docs/AGENT_STABLE.md first. Auto-context OFF; sufficiency on. Awaiting task."
