"""
Pipeline engine.

Orchestrates the three stages — recon → triage → report — over a set of
targets. Two operating modes, both driven from the same code path:

  * **Automated** (default): runs every stage end-to-end.
  * **Interactive / step-gated**: before each stage the engine calls the
    supplied ``confirm`` callback; returning False halts the pipeline cleanly.

Progress is surfaced through an ``on_event`` callback so the CLI, TUI, and web
dashboard can all render live status without the engine knowing which UI it is
talking to.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable, Optional

from ..providers import AIProvider, get_provider
from ..recon import get_modules
from ..triage import TriageAnalyzer
from .config import AppConfig
from .models import Run, RunStage
from .scope import Scope
from .store import RunStore

EventFn = Callable[[str, str], None]
ConfirmFn = Callable[[str], bool]


class Engine:
    def __init__(
        self,
        config: AppConfig,
        scope: Scope,
        provider: Optional[AIProvider] = None,
        store: Optional[RunStore] = None,
        on_event: Optional[EventFn] = None,
    ):
        self.config = config
        self.scope = scope
        self.store = store or RunStore(config.data_dir)
        self._provider = provider
        self._emit = on_event or (lambda stage, msg: None)

    # ---- provider ------------------------------------------------------------
    @property
    def provider(self) -> AIProvider:
        if self._provider is None:
            self._provider = get_provider(
                self.config.active_provider,
                self.config.provider_config(),
            )
        return self._provider

    # ---- pipeline ------------------------------------------------------------
    def run_pipeline(
        self,
        targets: list[str],
        interactive: Optional[bool] = None,
        confirm: Optional[ConfirmFn] = None,
        do_triage: bool = True,
    ) -> Run:
        interactive = self.config.interactive if interactive is None else interactive
        confirm = confirm or (lambda stage: True)

        allowed, refused = self.scope.filter_in_scope(targets)
        for t in refused:
            self._emit(RunStage.RECON.value, f"⛔ refused (out of scope): {t}")
        run = Run(targets=allowed)

        if not allowed:
            self._emit(RunStage.RECON.value, "No in-scope targets; nothing to do.")
            run.finished_at = datetime.now(timezone.utc)
            return run

        # --- Recon ---
        if not interactive or confirm(RunStage.RECON.value):
            self._run_recon(run, allowed)
        else:
            self._emit(RunStage.RECON.value, "Skipped by operator.")

        # --- Triage ---
        if do_triage and (not interactive or confirm(RunStage.TRIAGE.value)):
            self._run_triage(run)
        else:
            self._emit(RunStage.TRIAGE.value, "Skipped.")

        # --- Report (persist) ---
        if not interactive or confirm(RunStage.REPORT.value):
            path = self.store.save(run)
            self._emit(RunStage.REPORT.value, f"Saved run to {path}")

        run.finished_at = datetime.now(timezone.utc)
        self.store.save(run)
        return run

    def _run_recon(self, run: Run, targets: list[str]) -> None:
        module_classes = get_modules(self.config.recon.enabled_modules)
        if self.config.recon.passive_only:
            module_classes = [m for m in module_classes if True]  # all bundled are low-touch
        modules = [
            m(
                self.scope,
                timeout=self.config.recon.request_timeout,
                user_agent=self.config.recon.user_agent,
            )
            for m in module_classes
        ]
        self._emit(
            RunStage.RECON.value,
            f"Running {len(modules)} modules across {len(targets)} target(s)…",
        )

        jobs = [(mod, t) for mod in modules for t in targets]
        with ThreadPoolExecutor(max_workers=self.config.recon.max_concurrency) as pool:
            futs = {pool.submit(mod.run, t): (mod, t) for mod, t in jobs}
            for fut in as_completed(futs):
                mod, t = futs[fut]
                result = fut.result()
                run.results.append(result)
                if result.ok:
                    self._emit(
                        RunStage.RECON.value,
                        f"✓ {mod.name} on {t}: "
                        f"{len(result.assets)} assets, {len(result.findings)} findings",
                    )
                else:
                    self._emit(RunStage.RECON.value, f"✗ {mod.name} on {t}: {result.error}")

    def _run_triage(self, run: Run) -> None:
        findings = run.all_findings()
        if not findings:
            self._emit(RunStage.TRIAGE.value, "No findings to triage.")
            return
        prov = self.provider
        if not prov.is_available():
            self._emit(
                RunStage.TRIAGE.value,
                f"Provider '{prov.name}' not available — keeping heuristic severities.",
            )
            return
        self._emit(
            RunStage.TRIAGE.value,
            f"Triaging {len(findings)} findings with {prov.name} ({prov.config.model})…",
        )
        TriageAnalyzer(prov).triage_run(run)
        self._emit(RunStage.TRIAGE.value, "Triage complete.")
