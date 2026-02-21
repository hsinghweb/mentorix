---
name: agent-manager-skill
version: "1.0.0"
description: Manage local agent processes and logs using CLI recipes
intent_triggers: ["restart agent", "kill agent", "list agents"]
---

# Agent Manager Guide

Use existing runtime tools to execute process-level maintenance commands safely.

## Start an agent
Run:
`python agent-manager/scripts/main.py start <AGENT_ID>`

## List agents
Run:
`python agent-manager/scripts/main.py list`

## Monitor logs
Run:
`tail -f logs/<AGENT_ID>.log`
