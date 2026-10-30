# Example: RAG chat

A multi-turn support chat that retrieves fresh documentation chunks for every question. It shows the layout that matters most for retrieval-augmented apps:

```
system policy → FAQ + model table (static) → chat history (append-only) → retrieved chunks → question
```

The retrieved chunks change every turn, so they go **after** the history. The policy, the FAQ and the conversation so far are read from cache on every turn, and the chunks never pay a cache-write premium. That's the case where a provider's automatic caching does worst: it puts its entry at the very end, after the per-turn tail.

```console
uv run --env-file .env python examples/rag_chat.py anthropic   # or openai, gemini, litellm
```

Sample run on `claude-haiku-5-5` (2026-10-30), with answers shortened:

```text
Q: It happens mostly on the 2.4 GHz band. Which channel should I pick?
A: Pick whichever of channels 1, 6 or 11 is least crowded near you. ...
   cache read 6,796 of 7,769 input tokens (87%), ~$0.00051
   vs previous request: first differs at messages[0].content[0].text (last turn)

Q: Is WireGuard faster than OpenVPN on my model?
A: Yes. WireGuard is faster than OpenVPN on every Acme model, including your AX3000. ...
   cache read 7,349 of 8,304 input tokens (88%), ~$0.00042

call site   calls  hit rate  input   cache read  cache write  output  est $   top drift
rag.answer  4      88.8%     31,574  28,024      714          2,601   0.0020
```

`vs previous request: ... (last turn)` is what a healthy RAG loop looks like. Each request repeats the previous one exactly, except the previous final turn, whose retrieved chunks were deliberately not kept in history.

Things to copy into your own app:

- Build the `Prompt` fresh each turn; pass history as plain messages. You don't need to keep cache markers around; cachemaxxing places them.
- Keep retrieved chunks out of the stored history; pass them with `p.retrieved(...)`.
- Log `record(call_site, kwargs, response)` and run `cachemaxxing report` to watch the hit rate per call site.
- Replace `retrieve()` with your vector store; nothing else changes.

```python
--8<-- "examples/rag_chat.py"
```
