# neuroman/core.py
"""NeuroMan semantic orchestrator — session-aware async task router."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from rich.console import Console

from .auth import auth_status, ensure_claude_login
from .resilience import DegradedMode, ErrorKind, NeuroError
from .router import OmniRouteClient
from .session import SessionMemory
from .tools.ableton import AbletonController
from .tools.cline_bridge import dispatch_to_cline
from .tools.coder import dispatch_to_coder
from .tools.knowledge import format_context_block, search_vault
from .tools.web import handle_web_query

log = logging.getLogger("neuroman.core")

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def _parse_json_loose(text: str) -> dict[str, Any]:
    """Extract JSON object from raw LLM output; raise NeuroError if impossible."""
    raw = (text or "").strip()
    if not raw:
        raise NeuroError(
            message="Prazdny vystup modelu misto JSON.",
            kind=ErrorKind.MALFORMED,
            source="orchestrator",
        )
    candidates = [raw]
    m = _JSON_FENCE_RE.search(raw)
    if m:
        candidates.insert(0, m.group(1).strip())
    # try substring from first { to last }
    if "{" in raw and "}" in raw:
        candidates.append(raw[raw.find("{") : raw.rfind("}") + 1])

    last_err: Optional[Exception] = None
    for cand in candidates:
        try:
            data = json.loads(cand)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError as exc:
            last_err = exc
            continue
    raise NeuroError(
        message="LLM nevygenerovalo validni JSON strukturu.",
        kind=ErrorKind.MALFORMED,
        source="orchestrator",
        detail=repr(last_err),
    )


class NeuroManOrchestrator:
    """Semanticka vrstva smerovani uloh: OmniRoute + Producer Pal + coding agents."""

    def __init__(self, console: Console, session: Optional[SessionMemory] = None) -> None:
        self.console = console
        self.router = OmniRouteClient()
        self.ableton = AbletonController()
        self.session = session or SessionMemory.load_or_create(
            os.getenv("NEUROMAN_SESSION_ID")
        )
        # cline | claude | opencode
        self.coding_agent = os.getenv("NEUROMAN_CODING_AGENT", "cline").lower()
        self.degraded = DegradedMode()
        log.info(
            "orchestrator ready session=%s agent=%s",
            self.session.session_id,
            self.coding_agent,
        )

    async def aclose(self) -> None:
        try:
            self.session.save()
        except OSError as exc:
            log.warning("session save on close failed: %s", exc)
        await self.router.aclose()
        await self.ableton.aclose()

    # --- public API -------------------------------------------------------

    async def dispatch_task(self, prompt: str) -> None:
        prompt = prompt.strip()
        if not prompt:
            return

        ctx = self.session.context_block()
        try:
            with self.console.status("[cyan]Klasifikuji zamer (OmniRoute fast)…[/cyan]"):
                intent = await self.router.get_intent(prompt)
        except NeuroError as exc:
            self.degraded.mark("omniroute", exc.user_line())
            intent = OmniRouteClient._heuristic_intent(prompt)
            self.console.print(
                f"[yellow]Intent fallback (heuristic): {intent} — {exc.user_line()}[/yellow]"
            )

        self.session.add_user(prompt, intent=intent)
        self.console.print(f"[dim italic]Vektor ulohy: {intent} | session={self.session.session_id}[/dim italic]")
        if self.session.facts:
            facts = ", ".join(f"{k}={v}" for k, v in self.session.facts.items())
            self.console.print(f"[dim]Pamatuji: {facts}[/dim]")

        try:
            if intent == "CODE":
                await self._handle_code(prompt, ctx)
            elif intent == "ABLETON":
                await self._handle_ableton_task(prompt, ctx)
            elif intent == "MUSIC":
                await self._handle_music(prompt, ctx)
            else:
                text = await handle_web_query(prompt, self.router, self.console, context=ctx)
                if text:
                    self.session.add_assistant(text, intent=intent)
        except NeuroError as exc:
            log.exception("dispatch NeuroError")
            self.console.print(f"[bold red]{exc.user_line()}[/bold red]")
            self.session.add_assistant(exc.user_line(), intent=intent, error=True)
        except Exception as exc:  # noqa: BLE001
            log.exception("dispatch unexpected")
            msg = f"Neocekavana chyba: {exc}"
            self.console.print(f"[bold red]{msg}[/bold red]")
            self.session.add_assistant(msg, intent=intent, error=True)
        finally:
            try:
                self.session.save()
            except OSError as exc:
                log.warning("session save failed: %s", exc)

    # --- branches ---------------------------------------------------------

    async def _handle_code(self, prompt: str, ctx: str) -> None:
        agent = self.coding_agent
        # Enrich prompt with remembered musical facts (tempo -> script continuity)
        enriched = prompt
        if self.session.facts:
            fact_blob = json.dumps(self.session.facts, ensure_ascii=False)
            enriched = f"{prompt}\n\n[NeuroMan remembered facts]: {fact_blob}"

        if agent == "cline":
            self.console.print("[magenta]Handoff pro Cline (VS Code)…[/magenta]")
            path = await dispatch_to_cline(
                enriched,
                self.console,
                extra_context=ctx,
                session_id=self.session.session_id,
            )
            self.session.add_assistant(f"cline handoff -> {path}", intent="CODE")
            return

        if agent in ("claude", "opencode"):
            label = "Claude Code" if agent == "claude" else "OpenCode"
            self.console.print(f"[magenta]Deleguji na {label}…[/magenta]")
            rc = await dispatch_to_coder(
                enriched,
                self.console,
                agent_type=agent,
                extra_context=ctx,
                ensure_auth=(agent == "claude"),
            )
            if rc != 0 and agent == "claude":
                # autonomous fallback: still produce Cline handoff so work continues
                self.console.print(
                    "[yellow]Claude selhal — fallback na Cline handoff.[/yellow]"
                )
                self.degraded.mark("claude", f"exit={rc}")
                path = await dispatch_to_cline(
                    enriched,
                    self.console,
                    extra_context=ctx,
                    session_id=self.session.session_id,
                )
                self.session.add_assistant(
                    f"claude failed; cline handoff -> {path}", intent="CODE"
                )
            else:
                self.session.add_assistant(f"{agent} finished rc={rc}", intent="CODE")
            return

        self.console.print(f"[red]Neznamy NEUROMAN_CODING_AGENT={agent!r}[/red]")

    async def _handle_music(self, prompt: str, ctx: str) -> None:
        self.console.print("[yellow]Hudebni analyza…[/yellow]")
        system_msg = (
            "Jsi elitni hudebni producent, expert na neurofunk, kompozici, sound design a mix. "
            "Odpovidej analyticky a konkretne. Pokud znas tempo/tonalitu ze session, drz se jich."
        )
        vault_hits = search_vault(prompt)
        if vault_hits:
            self.console.print(f"[dim]Vault: {len(vault_hits)} relevantnich .md souboru[/dim]")
            system_msg += "\n\n" + format_context_block(vault_hits)
        if ctx:
            system_msg += f"\n\nSession context:\n{ctx}"
        # If user asks to generate a script after tempo was set, nudge toward CODE facts
        tempo = self.session.get_fact("tempo_bpm")
        if tempo and re.search(r"(?i)\b(script|kod|python|generuj)\b", prompt):
            system_msg += (
                f"\nUzivatel ma v session tempo {tempo} BPM — "
                "zahrn ho do jakehokoli generovaneho skriptu."
            )
        try:
            response = await self.router.generate_completion(prompt, system_message=system_msg)
            self.console.print(f"\n[bold yellow]Hudebni expertiza:[/bold yellow]\n{response}\n")
            self.session.add_assistant(response, intent="MUSIC")
            # re-extract facts from assistant (e.g. suggested tempo)
            self.session._extract_facts(response)
        except NeuroError as exc:
            self.degraded.mark("omniroute", exc.user_line())
            self.console.print(f"[red]{exc.user_line()}[/red]")
            self.session.add_assistant(exc.user_line(), intent="MUSIC", error=True)

    async def _handle_ableton_task(self, prompt: str, ctx: str) -> None:
        self.console.print("[blue]Producer Pal (Ableton Live)…[/blue]")
        set_state = await self.ableton.read_live_set()
        if "error" in set_state:
            self.degraded.mark("ableton", str(set_state.get("error")))
            self.console.print(f"[red]Ableton/Producer Pal: {set_state['error']}[/red]")
            # degraded: answer from session facts if possible
            tempo = self.session.get_fact("tempo_bpm")
            if tempo and re.search(r"(?i)\btempo|bpm\b", prompt):
                msg = f"Ableton offline — z session pamati: tempo={tempo} BPM."
                self.console.print(f"[yellow]{msg}[/yellow]")
                self.session.add_assistant(msg, intent="ABLETON", degraded=True)
            else:
                self.session.add_assistant(str(set_state["error"]), intent="ABLETON", error=True)
            return

        # remember key live-set fields
        patch: dict[str, Any] = {}
        for key in ("tempo", "timeSignature", "scale", "name"):
            if key in set_state:
                patch[key] = set_state[key]
        if patch:
            self.session.merge_tool_state({"live_set": patch})
            if "tempo" in patch:
                try:
                    self.session.set_fact("tempo_bpm", float(patch["tempo"]))
                except (TypeError, ValueError):
                    pass

        # compact state for prompt (avoid huge dumps)
        state_json = json.dumps(set_state, ensure_ascii=False)
        if len(state_json) > 6000:
            state_json = state_json[:6000] + "…"

        system_msg = f"""Jsi specializovany asistent pro ovladani Ableton Live pres Producer Pal API.
Aktualni serializovany stav projektu (Live Set): {state_json}

Session facts: {json.dumps(self.session.facts, ensure_ascii=False)}

Pokud odpoved na dotaz uz je obsazena ve stavu projektu (napr. Tempo, timeSignature,
pocet stop, scale), NEVOLEJ zadny nastroj - pouzij 'ppal-noop' s tou hodnotou v args.
Jinak analyzuj pozadavek a vygeneruj validni volani prislusneho nastroje.

POZOR: pouzivej VYHRADNE tato presna jmena nastroju (zadna jina neexistuji, nevymyslej si vlastni nazvy):
- 'ppal-read-live-set' {{include}} - precist globalni stav
- 'ppal-update-live-set' {{tempo, timeSignature, scale, locatorOperation, ...}} - zmenit tempo/scale/lokatory
- 'ppal-read-track' {{trackIndex|trackId, include}} - precist stopu
- 'ppal-create-track' {{count, type, name, ...}}
- 'ppal-update-track' {{ids, name, gainDb, pan, mute, solo, ...}}
- 'ppal-read-clip' {{clipId|slot, include}}
- 'ppal-create-clip' {{trackIndex, slot, length, notes, ...}}
- 'ppal-update-clip' {{ids, notes, transforms, warpMode, ...}}
- 'ppal-read-device' {{deviceId|path, include, maxDepth, paramSearch}} - precist nastaveni/parametry zarizeni (napr. Serum)
- 'ppal-create-device' {{deviceName, path, params}} - pridat novy device na stopu
- 'ppal-update-device' {{ids|path, params, actions, macroVariation, ...}} - JEDINY nastroj pro zmenu parametru
  existujiciho zarizeni (napr. Serum oscillator/filter/env hodnoty).
  DULEZITE presne tvary poli:
    - 'path' je KRATKY tvar 't<trackIndex>/d<deviceIndex>', napr. 't1/d0' (NE 'tracks/1/devices/0').
    - 'params' je POLE objektu {{"name": ..., "value": ...}}, NIKDY obycejny dict/objekt s klici.
      'value' je VZDY string (i pro cisla, napr. "35", ne 35).
    - Pro zjisteni presneho nazvu parametru NEJDRIV zavolej 'ppal-read-device' s paramSearch.
- 'ppal-delete' {{ids|path, type}}
- 'ppal-duplicate' {{id, type, count, ...}}
- 'ppal-select' {{id|trackIndex|sceneIndex|devicePath, ...}}
- 'ppal-playback' {{action, ...}} - play/stop/record
- 'ppal-library' {{action, kind, query, ...}} - hledani v Live browseru

Nastroj 'ppal-update-device-param' NEEXISTUJE - pro zmenu jakehokoli parametru zarizeni pouzij 'ppal-update-device'.
Odpovez STRIKTNE jako validni JSON objekt. Zadny markdown, zadny text okolo.
Priklad zmeny parametru: {{"tool": "ppal-update-device", "args": {{"path": "t1/d0", "params": [{{"name": "Osc 1 Unison Detune", "value": "35"}}]}}}}
Priklad noveho clipu: {{"tool": "ppal-create-clip", "args": {{"trackIndex": 0, "slot": "0/0", "length": "4bar", "notes": "[.]"}}}}
Priklad pro uz znamou hodnotu: {{"tool": "ppal-noop", "args": {{"answer": "Tempo je 120 BPM"}}}}
"""
        if ctx:
            system_msg += f"\nRecent dialogue:\n{ctx[-1500:]}"

        try:
            with self.console.status("[cyan]LLM generuje parametry pro Ableton…[/cyan]"):
                llm_response = await self.router.generate_completion(
                    prompt, system_message=system_msg, temperature=0.2
                )
            command_data = _parse_json_loose(llm_response)
        except NeuroError as exc:
            self.console.print(f"[red]{exc.user_line()}[/red]")
            if exc.kind == ErrorKind.MALFORMED:
                self.console.print(f"[dim]Surovy vystup:\n{(llm_response if 'llm_response' in dir() else '')}[/dim]")
            self.session.add_assistant(exc.user_line(), intent="ABLETON", error=True)
            return

        tool_name = command_data.get("tool")
        tool_args = command_data.get("args") or {}
        if not isinstance(tool_args, dict):
            tool_args = {}

        if tool_name == "ppal-noop":
            answer = str(tool_args.get("answer", "(bez odpovedi)"))
            self.console.print(f"\n[bold green]{answer}[/bold green]\n")
            self.session.add_assistant(answer, intent="ABLETON")
            return

        if not tool_name:
            self.console.print("[red]JSON bez pole 'tool'.[/red]")
            self.session.add_assistant("missing tool field", intent="ABLETON", error=True)
            return

        self.console.print(f"[dim]Nastroj: {tool_name} args={tool_args}[/dim]")
        result = await self.ableton.call_tool(str(tool_name), tool_args)
        if "error" in result:
            self.console.print(f"[red]Exekuce: {result['error']}[/red]")
            self.session.add_assistant(str(result["error"]), intent="ABLETON", error=True)
        else:
            pretty = json.dumps(result, indent=2, ensure_ascii=False)
            self.console.print(f"[bold green]Ableton OK:[/bold green]\n{pretty}")
            self.session.add_assistant(pretty[:2000], intent="ABLETON")
            self.session.merge_tool_state({"last_tool": tool_name, "last_result_keys": list(result)[:20]})

    # --- auth helper for CLI ----------------------------------------------

    async def login_claude(self) -> None:
        try:
            status = await ensure_claude_login(interactive=True)
            self.console.print(
                f"[green]Claude ready[/green] cli={status.claude_cli} "
                f"key={status.anthropic_key_present} src={status.source}"
            )
        except NeuroError as exc:
            self.console.print(f"[red]{exc.user_line()}[/red]")

    def status_line(self) -> str:
        a = auth_status()
        return (
            f"session={self.session.session_id} | agent={self.coding_agent} | "
            f"claude_cli={a.claude_cli} key={a.anthropic_key_present} | "
            f"{self.degraded.summary()}"
        )
