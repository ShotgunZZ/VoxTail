# Contributing to VoxTail

Thanks for your interest in contributing! Here's how to get started.

## Getting Started

1. Fork the repo and clone locally
2. Follow the [Run Locally](README.md#option-2-run-locally) instructions in the README
3. The app runs at http://localhost:8000

## Development Notes

- **No build step** — the frontend is vanilla JS with ES modules
- **Service worker caching** — after changing any file in `static/`, bump `CACHE_NAME` in `sw.js`
- **CLAUDE.md** has the full architecture reference — start there to understand the codebase

## Making Changes

1. Create a branch from `main`
2. Make your changes
3. Test locally — make sure the app starts and your feature works
4. Submit a pull request against `main`

## Pull Request Guidelines

- One feature or fix per PR
- Describe **what** changed and **why** in the PR description
- Keep changes focused — avoid unrelated reformatting or refactoring

## Code Style

- **Python:** Follow existing patterns — FastAPI, async/await, type hints where used
- **JavaScript:** ES modules, no build tools, use `escapeHtml()` for user-generated content
- **CSS:** Use design tokens from `tokens.css` for colors, fonts, spacing

## Good First Issues

Look for issues labeled [`good first issue`](../../labels/good%20first%20issue) — these are scoped for new contributors.

## Questions?

Open an issue — happy to help.
