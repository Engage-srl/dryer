# dryer — Kotlin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `dryer` riconosce i sorgenti `.kt` e segnala coppie di funzioni Kotlin strutturalmente duplicate, come fa per Java.

**Architecture:** Un picker Kotlin in `extract.py` (stesse funzioni che `crapper` Kotlin valuta) e poche voci Kotlin nelle tabelle di `astnorm.py` (identificatori, letterali, operatori, chiamate, navigazione). Nessun modulo nuovo di logica: dryer è già generico sui nodi tree-sitter.

**Tech Stack:** Python ≥ 3.11, `tree-sitter-language-pack` (grammatica `kotlin`), pytest.

**Spec:** `Engage-srl/crapper` → `docs/superpowers/specs/2026-10-26-kotlin-support-design.md` (sezione "Cosa conta come funzione"; vale anche qui). Decisioni proprie di questo piano: sotto.

## Global Constraints

- Fork `Engage-srl/dryer`, allineabile con upstream: solo righe di aggancio nei file esistenti, nessun test esistente modificato (solo casi aggiunti).
- Nessuna nuova dipendenza. `language="kotlin"`.
- Funzioni confrontate = quelle che `crapper` Kotlin valuta: `fun` con corpo in class/interface/object/companion/enum entry/top-level (estensioni incluse), getter/setter con corpo. Esclusi: `inline`, astratte, costruttori, `init`, funzioni locali, membri di `object` anonimi, lambda (restano nella funzione che le contiene).
- `.kt` sì, `.kts` no; directory `.claude` saltata (come in crapper).
- Ogni funzione nuova `CRAP < 10` (verifica con `~/sviluppo/crapper/crapper` nel Task 3).
- Baseline: `.venv/bin/pytest -q` → 80 passed.

## Nodi Kotlin (verificati sulla grammatica)

- chiamata: `call_expression` = [callee, `call_suffix`]; `call_suffix` contiene `value_arguments` e/o `annotated_lambda`.
- accesso membro: `navigation_expression` = [receiver, `navigation_suffix`]; `navigation_suffix` = [token `.` o `?.`, `simple_identifier`].
- identificatori: `simple_identifier`, `type_identifier`.
- letterali: `integer_literal`, `long_literal`, `hex_literal`, `bin_literal`, `real_literal`, `unsigned_literal`, `character_literal`, `boolean_literal`, `string_literal` (con interpolazione se contiene `interpolated_identifier` o `interpolated_expression`), `null` (token).
- operatori aggiuntivi rispetto alle tabelle esistenti: `?:`, `!!`, `..`, `as`, `as?`, `is`, `!is`, `in`, `!in`.

## Review Focus

1. `a.size` vs `a.count` (proprietà) → stessa forma; `xs.filter {}` vs `xs.map {}` (metodo chiamato) → forme diverse. (Task 1)
2. Stringa interpolata `"v=$a"` vs letterale `"v"` → non sono lo stesso letterale. (Task 1)
3. Due funzioni identiche tranne `?.` al posto di `.` → score < 1.0 (l'operatore resta nella forma). (Task 1)
4. Getter custom su riga propria (fratello di `property_declaration` nella grammatica) → è un candidato. (Task 1)
5. File con errori di parsing → nessun crash. (Task 1)

---

### Task 1: Picker e normalizzazione Kotlin

**Files:**
- Modify: `src/dryer/discover.py` (`".kt": "kotlin"` in `EXTENSIONS`, `".claude"` in `SKIP_DIRS`)
- Modify: `src/dryer/extract.py` (`_kotlin_nodes`, voce `"kotlin": ("kotlin", _kotlin_nodes)` in `_PICKERS`, docstring)
- Modify: `src/dryer/astnorm.py` (voci Kotlin nelle tabelle; gestione `call_suffix` / `navigation_suffix`)
- Test: `tests/test_kotlin.py` (nuovo)

**Interfaces:**
- Produces: `entries_in_source("kotlin", source, path, file)` → `(list[Entry], None)`.

- [ ] **Step 1: Write failing tests** in `tests/test_kotlin.py`, riusando lo stile di `tests/test_languages.py` (`write_source`, `pairs` con `threshold=0.99`, `forms`). Sorgenti multilinea realistici.
  - `test_kotlin_matches_renamed_locals`: `left.kt` `fun alpha(xs: List<Int>): List<Int> {\n    val ys = filter(xs, odd)\n    return map(ys, inc)\n}` e `right.kt` con `beta/items/kept/even/dec` → una coppia, `language == "kotlin"`, `score == 1.0`.
  - `test_kotlin_member_calls_keep_their_names`: `xs.filter { it > 0 }.size` vs `xs.map { it > 0 }.size` → nessuna coppia a 0.99; `xs.filter { it > 0 }.size` vs `ys.filter { it > 1 }.count` → coppia a 1.0.
  - `test_kotlin_safe_call_is_part_of_the_shape`: `a?.trim()` vs `a.trim()` (corpi altrimenti identici) → nessuna coppia a 0.99.
  - `test_kotlin_interpolated_string_is_not_a_plain_literal`: i fingerprint di `return "v=$a"` e `return "v"` differiscono.
  - `test_kotlin_candidates_match_crapper`: un file con `class Box` (`fun place()`, getter custom su riga propria, `inline fun inl()`, `abstract fun abs()`, `init {}`, `fun outer() { fun local() {}; val o = object : Runnable { override fun run() {} } }`, `companion object { fun make() {} }`), un `enum class` con entry con corpo, una top-level `fun String.shout() = uppercase()` → gli span di `forms("kotlin", ...)` corrispondono esattamente a `place`, getter, `outer`, `make`, la funzione nell'entry, `shout` (asserire su `start_line`).
  - `test_kotlin_detection`: `language_of("A.kt") == "kotlin"`, `language_of("build.gradle.kts") is None`; un `.kt` sotto `.claude/worktrees/` non è nei file scansionati.
  - `test_kotlin_broken_source_does_not_raise`: `forms("kotlin", "fun broken( {\n", "B.kt")` non solleva.
- [ ] **Step 2: Run** `.venv/bin/pytest -q tests/test_kotlin.py` — Expected: FAIL (lingua sconosciuta / nessuna entry).
- [ ] **Step 3: Implement.**
  - `_kotlin_nodes(data, root) -> list`: stesse regole di `crapper/src/crapper/languages/kotlin.py` (`_entry_name` / `_inside_executable` / `_is_inline`), riscritte qui (dryer non importa crapper). Gli accessor su riga propria vanno inclusi anche se non sono figli di `property_declaration`.
  - `astnorm.py`: `simple_identifier` in `_IDENTIFIERS`; letterali Kotlin in `_LITERALS`, e `_is_literal` esclude `string_literal` con figlio `interpolated_identifier`/`interpolated_expression`; operatori sopra in `_OPERATORS`; `call_expression` è già in `_CALLS`: `call_suffix` deve contare come lista argomenti (in `_ARG_LISTS`); `navigation_expression` in `_ATTRIBUTES`; il nome del membro sta dentro `navigation_suffix`, quindi `_attr_jobs`/`_assemble_attr` devono trattare un `navigation_suffix` finale come il suo `simple_identifier` (in testa: nome mantenuto; altrimenti `symbol` generico) e conservare il token `?.` come operatore.
- [ ] **Step 4: Run** `.venv/bin/pytest -q` — Expected: tutti PASS (80 + nuovi).
- [ ] **Step 5: Commit** `Add Kotlin to dryer`.

### Task 2: Help, README, descrizione

**Files:** `src/dryer/cli.py` (HELP), `README.md` (riga Kotlin nella tabella "what is compared"), `pyproject.toml` (description), `tests/test_kotlin.py`.

- [ ] **Step 1: Failing test** `test_help_mentions_kotlin`: `"Kotlin (.kt)" in HELP` (importare `HELP` da `dryer.cli`).
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement**: `Kotlin (.kt)` nell'elenco lingue; riga README `| Kotlin | functions with a body, custom accessors | inline and abstract functions, constructors, init blocks, local functions, members of anonymous objects |`; Kotlin nella description.
- [ ] **Step 4: Run** `.venv/bin/pytest -q` — Expected: PASS.
- [ ] **Step 5: Commit** `Document Kotlin support`.

### Task 3: Verifica

- [ ] **Step 1:** `cd ~/sviluppo/dryer && ~/sviluppo/crapper/crapper --threshold 10 src/dryer/extract.py src/dryer/astnorm.py` — Expected: exit 0. Se no, spezzare e ritestare; commit `Bring Kotlin code under CRAP 10`.
- [ ] **Step 2:** `cd ~/sviluppo/Artemis/eARTS && ~/sviluppo/dryer/dryer -s apt2artemis | head -30` — Expected: exit 0, coppie Kotlin con score ≥ 0.8 o nessuna; nessun crash. Poi `-s EDEP` per tempi su un modulo grande (riportare durata).
- [ ] **Step 3:** riportare in chat: numero di coppie Kotlin, prime 5, durata.
