---
description: Start the Tvashtr Ollama-compatible endpoint that serves enhanced tvashtr/<model> names
argument-hint: [--port 11435]
---

Use the tvashtr skill. Start `serve` in the background with: $ARGUMENTS

Confirm it is up by requesting `/api/tags`, then tell the user the base URL and how to point
Continue, Aider or Open WebUI at it (Ollama provider, base URL `http://127.0.0.1:<port>`, model
`tvashtr/<tag>`; OpenAI-compatible clients use `<base>/v1`).
