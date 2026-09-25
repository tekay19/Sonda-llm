# Sonda-llm

An AI assistant that runs entirely on your own computer. It can research the web and carry out tasks in your
browser. The model runs locally through Ollama, so your chats, memory and browsing never go to a third-party
server. Sonda goes online only to search, read pages and do the tasks you give it.

The interface is in Turkish, and Sonda answers in Turkish by default. It reads English and Turkish sources alike.

## Features

- **Web research:** Sonda searches DuckDuckGo, Bing and Brave at the same time, sending Turkish and English queries
  together. It merges the results and ranks them by semantic similarity, then reads the best pages (HTML and PDF)
  in parallel.
- **Every claim has a source:** click a `[1]` or `[2]` marker in an answer to open its source.
- **Two research modes:**
  - *Fast:* searches for your question, reads the results, and searches again if needed.
  - *Deep research:* splits the question into sub-questions, runs a second round of searches for anything still
    missing, and writes a report with headings.
- **Tools:** a calculator for exact arithmetic and a date tool for date and day calculations. Reasoning mode turns
  on automatically for hard questions.
- **Follow-up questions:** questions like "what about the price?" or "which was the second one?" take the previous
  answer and its sources into account.
- **Memory:** Sonda remembers what it learns about you across chats, such as your name, preferences and projects.
  You can view and delete this in the *Memory* panel in the left menu.
- **Task mode:** Sonda opens a new tab in your own Chrome and works in it for you. It searches Google, visits
  sites, scrolls, opens "show more" sections, fills in forms, and collects and compares information.
  - It plans according to how deep the task is (simple, medium or deep) and doesn't finish until it has checked
    enough different sites.
  - It remembers every page it visited during the task, what it did there and what it found. It also works on
    English-language sites.
  - It uses the sessions you're already logged into in Chrome. If a task includes a password for a site, it types
    it only on that site. On two-factor authentication pages it pauses, then continues on its own once you've
    verified.
  - It works in plain, human-readable messages: while it works it tells you what it's doing, and every task ends
    with a clear status (done, stopped, your turn, or error).
  - **Safety, enforced in code:**
    - Sonda never types into card number, CVV, IBAN or verification code fields.
    - It never presses pay, buy, place-order, send, delete or confirm buttons.
    - When it reaches one of these steps, it stops, highlights the spot in Chrome and waits for you to press
      "Continue".
    - It ignores instructions written into web pages, such as "AI assistant, do this".
    - A password you give it can't be written into any URL or any other field.
  - **First-time setup:** open `chrome://inspect/#remote-debugging` in Chrome and turn the switch on once. After the
    Sonda server starts, Chrome asks for permission once on the first task.
- **Chat-style interface:** chat history, search, renaming, message editing, regenerating answers, suggested
  follow-up questions, export to Markdown, light and dark themes.

## Installation

Requirements: Python 3.11+ and [Ollama](https://ollama.com).

```bash
# Models
ollama pull qwen3.6:35b-a3b   # main model (fast MoE, ~23 GB)
ollama pull bge-m3            # embedding model used to rank page chunks

# Python environment
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt     # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS / Linux
.venv\Scripts\python -m playwright install chromium   # used by the tests
```

Optional models: `qwen3.8:27b` (higher quality but slower) and `qwen2.5:7b` (very fast). The model picker in the
interface shows only the models you have installed.

## Running

On Windows, double-click `baslat.bat`, or run:

```bash
.venv\Scripts\python server.py
```

Then open **http://localhost:8765** in your browser.

## Hardware

Tested on a laptop with 64 GB RAM and 6 GB VRAM (RTX 4050). The MoE model reads input at about 400 tokens per
second and writes about 36 tokens per second. In fast mode, answers take 15 to 60 seconds, and deep research
reports take 2 to 3 minutes. Most of the model runs on the CPU on this machine, so long browser tasks can take
10 to 25 minutes.

## Project layout

| Path | Purpose |
|---|---|
| `server.py` | Launcher (`sonda.sunucu`) |
| `sonda/asistan.py` | Entry point: runs research or a task depending on the mode; follow-up suggestions, memory, titles |
| `sonda/sunucu.py` | FastAPI server, streaming (SSE) and task-command endpoints |
| `sonda/yonlendirme.py` | In task mode, decides whether a message is a browser task, chat or a quick question |
| `sonda/ortak.py` | Model settings, today's date, model calls that return JSON |
| `sonda/web.py` | Multi-engine search, re-ranking, parallel page and PDF reading |
| `sonda/hesap.py` | Safe calculator and date calculations |
| `sonda/hafiza.py` | Persistent memory across chats (`veri/hafiza.json`) |
| `sonda/koruma.py` | Task-mode safety rules |
| `sonda/arastirma/` | Fast and deep research: tools, sources, prompts |
| `sonda/tarayici/` | Chrome connection (CDP), tab control, JavaScript injected into pages |
| `sonda/gorev/` | Task mode: settings, prompts, page summary / 2FA / page memory, decisions, actions, loop, management, debug logs |
| `static/index.html` | Interface |
| `tests/` | Unit and integration tests, local fake sites, real-model and real-web scenarios |

Task debug logs are written to `veri/gorev_kayitlari/`, with passwords masked. They record what the model saw and
decided at each step. The `veri/` folder is never committed.

## Tests

```bash
.venv\Scripts\python -m pytest                          # fast tests (safety rules, browser, task loop, server, UI)
.venv\Scripts\python -m pytest -m model                 # tasks on local fake sites with the real model (slow)
set SONDA_YEREL_TARAYICI=acik && .venv\Scripts\python tests\gorev_calistir.py <label>   # real-web tasks
```

If `SONDA_YEREL_TARAYICI` is set to `acik` (visible) or `gizli` (headless), Sonda uses Playwright's Chromium instead
of your Chrome.

Question set for the research modes:

```bash
.venv\Scripts\python tests\calistir.py <label>            # all questions
.venv\Scripts\python tests\calistir.py <label> 3,17,46    # selected questions
.venv\Scripts\python tests\calistir.py <label> --devam    # resume a stopped run
```

This question set covers trick questions, exact arithmetic, date calculations, false premises, current events,
instruction following, coding questions, follow-up questions and memory.
