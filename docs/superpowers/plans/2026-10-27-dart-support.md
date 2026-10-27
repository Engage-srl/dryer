# dryer — Dart/Flutter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `dryer` riconosce i sorgenti `.dart` e segnala coppie di funzioni Dart strutturalmente duplicate.

**Architecture:** Picker Dart in `extract.py` (stesse entry di `crapper` Dart, riscritte qui) e voci Dart in `astnorm.py` (letterali, nomi chiamati nelle catene `identifier`/`selector`). In Dart firma e corpo sono fratelli: il picker restituisce il `function_body` da normalizzare e la riga di inizio della firma.

**Tech Stack:** Python ≥ 3.11, `tree-sitter-language-pack` (grammatica `dart`), pytest.

**Spec:** `Engage-srl/crapper` → `docs/superpowers/specs/2026-10-27-dart-support-design.md`.

## Global Constraints

- Solo righe di aggancio nei file esistenti; nessun test esistente modificato; nessuna nuova dipendenza.
- Entry = quelle dello spec (factory sì, costruttori generativi no, locali e closure dentro la funzione).
- Generati e test esclusi come in crapper; `.dart_tool` saltata.
- Le nuove voci di `astnorm` non devono cambiare i fingerprint delle altre lingue (lezione Kotlin: controllare che i tipi di nodo/token aggiunti non esistano in altre grammatiche, altrimenti limitarli al contesto Dart).
- Ogni funzione nuova `CRAP < 10`. Baseline: `.venv/bin/pytest -q` → 90 passed.

## Review Focus

1. `xs.where(...)` vs `xs.map(...)` → forme diverse; `a.length` vs `a.size` (proprietà) → stessa forma. (Task 1)
2. `a?.b` vs `a.b` → score < 1.0. (Task 1)
3. Stringa con `${}` vs letterale semplice → diverse. (Task 1)
4. Commento/annotazione tra firma e corpo → entry mantenuta. (Task 1)
5. Widget `build()` quasi identici in due file (caso tipico Flutter) → coppia trovata. (Task 1)

---

### Task 1: Picker e normalizzazione Dart

**Files:**
- Modify: `src/dryer/discover.py` (`.dart`, generati → `None` in `language_of`, `.dart_tool`, test Dart), `src/dryer/extract.py` (`_dart_nodes`; `_tree_entries` accetta dal picker una coppia `(nodo_da_normalizzare, nodo_di_inizio)`), `src/dryer/astnorm.py`
- Test: `tests/test_dart.py`

**Interfaces:**
- Produces: `entries_in_source("dart", source, path, file)` → `(list[Entry], None)`, `start_line` = riga della firma, `end_line` = fine del corpo.

- [ ] **Step 1: Write failing tests** (stile `tests/test_kotlin.py`):
  - `test_dart_matches_renamed_locals` (due file, `filter`/`map` come in Kotlin) → una coppia, `language == "dart"`, score 1.0.
  - `test_dart_member_calls_keep_their_names` (Review Focus 1).
  - `test_dart_null_aware_access_is_part_of_the_shape` (Review Focus 2).
  - `test_dart_interpolated_string_is_not_a_plain_literal` (Review Focus 3).
  - `test_dart_candidates_match_crapper`: stesso sorgente del test entry di crapper Dart → `start_line` attese.
  - `test_dart_flutter_build_methods_pair` (Review Focus 5): due `Widget build(BuildContext context) { return Padding(padding: ..., child: Text(title)); }` con nomi diversi → coppia.
  - `test_dart_detection`, `test_dart_broken_source_does_not_raise`.
  - `test_other_languages_keep_their_fingerprints`: fingerprint di un metodo Java, una funzione TypeScript e una Python prima/dopo (valori fissati nel test) invariati.
- [ ] **Step 2: Run** `.venv/bin/pytest -q tests/test_dart.py` — Expected: FAIL.
- [ ] **Step 3: Implement**: picker come crapper Dart (senza importarlo). `astnorm`: `decimal_floating_point_literal` e `null_literal` già presenti; `string_literal` con `template_substitution` non è letterale; in una sequenza di figli, un `identifier` (anche dentro `unconditional_assignable_selector` / `conditional_assignable_selector`) seguito da `selector` con `argument_part` resta come nome chiamato; gli altri `identifier` diventano `symbol`; il token `?.` resta.
- [ ] **Step 4: Run** `.venv/bin/pytest -q` — Expected: tutti PASS.
- [ ] **Step 5: Commit** `Add Dart to dryer`.

### Task 2: Documentazione e verifica

- [ ] **Step 1:** HELP `Dart (.dart)`, riga README `| Dart | functions, methods, getters, setters, operators, factory constructors | generative constructors, abstract and external members, local functions, closures, generated files |`, description; test `test_help_mentions_dart`. Commit `Document Dart support`.
- [ ] **Step 2:** `crapper --threshold 10 src/dryer/extract.py src/dryer/astnorm.py` — Expected: exit 0.
- [ ] **Step 3:** `cd ~/sviluppo/gap_fleet && dryer -s packages/gap_core` e `dryer -s packages` (tempo). Riportare numero di coppie, prime 5, durata.
- [ ] **Step 4:** `CLOSE=1` sull'ultimo commit.
