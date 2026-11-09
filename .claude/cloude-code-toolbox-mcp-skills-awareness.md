# Claude Code ToolBox — MCP & Skills awareness

_Generated: 2026-11-09T19:22:46.751Z_

## How to use this report

- **Saved copy:** This file is **`.claude/cloude-code-toolbox-mcp-skills-awareness.md`** — refreshed whenever the toolbox runs an MCP & Skills scan (including on workspace open when auto-scan is enabled). It is meant for **Claude Code workspace context** together with `CLAUDE.md` (which gets a shorter replaceable summary when auto-merge is on).
- **MCP:** Lists **configured** servers from Claude Code config (`~/.claude.json` for user scope, `.mcp.json` for project scope). Use `/mcp` in the Claude Code panel to connect servers for your session.
- **Skills:** **On-disk** folders with `SKILL.md`. Claude Code does not auto-load them; attach `SKILL.md` or paths in chat when useful.
- **Task routing:** When the user’s request matches a server’s purpose (e.g. Confluence → Confluence/Atlassian MCP), prefer that **server id** from the tables below.

---

## MCP — workspace

Workspace `mcp.json` _(folder: HOS)_

- **c:\Users\krar9\Documents\GitHub\HOS\.mcp.json** — _File missing_

_No active workspace servers in mcp.json._

## MCP — user profile

- **C:\Users\krar9\.claude.json** — _File exists — no servers defined_

_No active user-scoped servers in mcp.json._

## Skills (local `SKILL.md` folders)

### Project-scoped

_None found (or no workspace open)._

### User-scoped

- **skill-creator** — `C:\Users\krar9\.claude\skills\skill-creator`
  - Create new skills, modify and improve existing skills. Use when users want to create a skill from scratch, edit, or optimize an existing skill.

- **automate** — `C:\Users\krar9\.agents\skills\automate`
  - Use this skill to create Codex Automations.

- **autopilot** — `C:\Users\krar9\.agents\skills\autopilot`
  - >-

- **canvas** — `C:\Users\krar9\.agents\skills\canvas`
  - >-

- **create-hook** — `C:\Users\krar9\.agents\skills\create-hook`
  - >-

- **create-rule** — `C:\Users\krar9\.agents\skills\create-rule`
  - >-

- **create-skill** — `C:\Users\krar9\.agents\skills\create-skill`
  - >-

- **create-subagent** — `C:\Users\krar9\.agents\skills\create-subagent`
  - >-

- **deploy-with-vercel** — `C:\Users\krar9\.agents\skills\deploy-with-vercel`
  - >-

- **developing-with-streamlit** — `C:\Users\krar9\.agents\skills\developing-with-streamlit`
  - Use for ALL Streamlit tasks: creating, editing, debugging, beautifying, styling, theming, optimizing, or deploying Streamlit apps. Also custom components, st.components.v2, HTML/JS/CSS work. Discovers and loads version-m

- **goal** — `C:\Users\krar9\.agents\skills\goal`
  - Set a goal that Codex will pursue to completion.

- **loop** — `C:\Users\krar9\.agents\skills\loop`
  - >-

- **migrate-to-skills** — `C:\Users\krar9\.agents\skills\migrate-to-skills`
  - >-

- **new-repo** — `C:\Users\krar9\.agents\skills\new-repo`
  - >-

- **onboard** — `C:\Users\krar9\.agents\skills\onboard`
  - >-

- **origin** — `C:\Users\krar9\.agents\skills\origin`
  - >-

- **rename-chat** — `C:\Users\krar9\.agents\skills\rename-chat`
  - >-

- **review** — `C:\Users\krar9\.agents\skills\review`
  - Review code changes with the Bugbot or Security Review subagent.

- **review-bugbot** — `C:\Users\krar9\.agents\skills\review-bugbot`
  - Review code changes with Bugbot subagent.

- **review-security** — `C:\Users\krar9\.agents\skills\review-security`
  - Review code changes with Security Review subagent.

- **sdk** — `C:\Users\krar9\.agents\skills\sdk`
  - >-

- **share** — `C:\Users\krar9\.agents\skills\share`
  - >-

- **shell** — `C:\Users\krar9\.agents\skills\shell`
  - >-

- **split-to-prs** — `C:\Users\krar9\.agents\skills\split-to-prs`
  - >-

- **statusline** — `C:\Users\krar9\.agents\skills\statusline`
  - >-

- **update-cli-config** — `C:\Users\krar9\.agents\skills\update-cli-config`
  - >-

- **update-cursor-settings** — `C:\Users\krar9\.agents\skills\update-cursor-settings`
  - >-

---

## Suggested next steps

- **MCP:** Use this extension’s hub **MCP** tab, or `claude mcp list` in the terminal. In Claude Code, use `/mcp` to connect servers for the session.
- **Edit config:** Open `~/.claude.json` (user MCP) or `<workspace>/.mcp.json` (project MCP) via the extension commands.
- **Refresh this report:** run **Intelligence — scan MCP & Skills awareness** again after changing MCP config or adding skills.

_Report from Claude Code ToolBox extension._
