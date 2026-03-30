## Context

The repository currently has no automated way to test the GitHub Pages site locally. Developers need to manually run Jekyll commands. Following GitHub's official documentation, we can create a simple bash script that wraps the necessary commands.

## Goals / Non-Goals

**Goals:**
- Provide a one-command solution to run Jekyll locally
- Support live reload for development workflow
- Output clear information about the local server URL

**Non-Goals:**
- Dependency management (assumes `jekyll` is in PATH)
- Docker/containerization
- Production deployment automation
- Windows support (focus on Unix-like systems with bash)

## Decisions

**Script Language: Bash**
- Use bash for simplicity and portability on Unix-like systems
- Rationale: GitHub Pages/Jekyll development typically happens on macOS/Linux

**Command Structure: Simple**
1. Run `jekyll serve` from `src/` directory with live reload
- Rationale: Assumes Jekyll is already available in PATH, serves content from `src/` subdirectory

**Live Reload: Enabled by default**
- Use `--livereload` flag for automatic page refresh
- Rationale: Improves development experience

**Port: Default 4000**
- Use Jekyll's default port, show URL in output
- Rationale: Standard convention, easy to remember

## Risks / Trade-offs

- **Dependency on Jekyll in PATH** → Mitigation: Script comments document the requirement
- **Port conflicts** if 4000 is in use → Mitigation: Jekyll will report this; user can specify alternate port manually
- **Generated `_site/` directory** → Mitigation: Added to `.gitignore` to prevent accidental commits
- **No Windows native support** → Mitigation: Document WSL or Git Bash as alternatives; script focuses on primary dev platforms
