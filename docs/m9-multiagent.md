# M9 — Multi-agent orchestration

**Branch:** `milestone/m9-multiagent`

## Acceptance

| Item | Status |
|------|--------|
| Attach multiple agents to session | Done |
| Event subscription per agent | Done |

## API

```python
async with Browser() as browser:
    page = await browser.set_content(html)
    session = browser.create_multi_agent_session()
    session.bind_page(page)

    navigator = session.attach("nav", role="navigator")
    filler = session.attach("form", role="input")

    navigator.subscribe(on_event, event_type="navigation")
    filler.subscribe(on_event)  # all events

    async def fill_form():
        await page.fill("#email", "a@b.c")

    await filler.run(fill_form())  # holds session lock
```

Commands should use `agent.run(coro)` when concurrent agents might race.
