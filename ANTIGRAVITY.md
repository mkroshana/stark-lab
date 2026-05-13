# Antigravity Agent - Stark Lab Wiki Schema

You are an agent operating on the **Stark Lab LLM Wiki**. Your goal is to maintain and query a persistent knowledge base.

## Foundation
This wiki follows the pattern defined in `D:\Brain\Stark Lab\GEMINI.md`. You must adhere to the same operational mandates.

## Core Directories (Absolute Paths)
- **Sources**: `D:\Brain\Stark Lab\sources\`
- **Wiki**: `D:\Brain\Stark Lab\wiki\`

## Operational Rules
1. **Consistency**: Always check `D:\Brain\Stark Lab\wiki\index.md` before creating new pages to avoid duplication.
2. **Persistence**: Do not just answer questions; if an answer is valuable, offer to save it as a new page in the wiki directory.
3. **Cross-Linking**: Every new page must use `[[Page Name]]` for Obsidian-style links and be added to the index.
4. **Logging**: Every operation must be appended to `D:\Brain\Stark Lab\wiki\log.md`.

## Integration with Gemini CLI
The Gemini CLI agent handles the heavy infrastructure and complex ingestions. Use your unique capabilities to:
- Perform quick lookups.
- Refine existing wiki pages.
- Handle chat-based queries against the wiki.

## Schema Reference
Refer to `D:\Brain\Stark Lab\GEMINI.md` for the full operational logic (Ingest, Query, Lint).
