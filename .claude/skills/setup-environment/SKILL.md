---
name: setup-environment
description: "Use to build a durable working environment for a project instead of starting every chat from scratch — a CLAUDE.md with working rules, an always-do / ask-first / never-do guardrail split, optional tool-level hooks for hard rules, and pointers to a knowledge base. Trigger when setting up a new project/repo, when the user wants Claude to stop re-explaining preferences each time, wants guardrails/rules/'pravidlá', wants to set up CLAUDE.md, or types /setup-environment."
---

# /setup-environment — Vrstva 3: Environment

**Spec a Verifier potrebujú kde žiť.** Toto je dielňa: prestaň každú reláciu začínať od nuly a postav systém, ktorý sa časom zlepšuje (kompounduje).

## Prečo to existuje

Väčšina ľudí používa dielňu zakaždým nanovo — jeden dlhý chat nie je systém. Prostredie znamená, že AI má **pravidlá práce, tvoje preferencie, znalostnú bázu, opakovateľné postupy a guardraily** vždy poruke. Toto je tvoj svet a AI v ňom žije, nie naopak.

## Čo postaviť

### A) CLAUDE.md — pravidlá práce

`CLAUDE.md` sa Claudovi automaticky injektuje pri každom prompte. Je to prvá vec, ktorú prečíta. Použi tento základný template a priprav ho na mieru projektu:

```text
# Ako máš pracovať

Pred každou viac-krokovou úlohou:
1. najprv identifikuj cieľ,
2. vytvor krátku špecifikáciu,
3. navrhni verifikačný plán,
4. rozdeľ prácu na malé checkpointy,
5. nepokračuj do ďalšej fázy, kým nie sú jasné nejasnosti alebo predpoklady.

# Pravidlá kvality

- Nepredstieraj istotu.
- Označ všetky predpoklady.
- Pri dôležitých tvrdeniach uveď, ako ich overiť.
- Ak chýba kontext, najprv sa spýtaj alebo navrhni najpravdepodobnejší predpoklad.
- Výstupy majú byť konkrétne, nie všeobecné.

# Nikdy nerob

- Nemeň kritické súbory bez potvrdenia.
- Nevymýšľaj dáta.
- Neodstraňuj existujúcu funkcionalitu bez upozornenia.
- Nerob veľké refaktory bez samostatnej špecifikácie.
```

Do CLAUDE.md tiež stručne popíš: ako je repo/workspace usporiadané, aké skilly máš a kedy ich použiť, kde leží znalostná báza, a kľúčové pravidlá.

### B) Guardraily: always do / ask first / never do

Rozdeľ právomoci podľa ceny chyby:

```text
ALWAYS DO (na autopilota):
- oprav preklepy, navrhni štruktúru, vytvor checklist,
- skontroluj konzistenciu, navrhni ďalšie kroky.

ASK FIRST (vyžiadaj potvrdenie):
- zmeniť positioning, prepísať veľkú časť textu, refaktorovať architektúru,
- odoslať email, zverejniť obsah, zmeniť cenotvorbu alebo ponuku.

NEVER DO (nikdy):
- vymýšľať čísla, mazať dáta, meniť produkčné súbory bez schválenia,
- posielať klientom niečo bez review,
- tvrdiť, že niečo overila, ak to reálne neoverila.
```

### C) Tvrdé pravidlá cez hooky (nie iba prosba)

Pravidlo v CLAUDE.md je *žiadosť* — AI ho môže ignorovať. Pri kritických veciach to musí byť vynútené na úrovni nástroja: napr. `PreToolUse` hook, ktorý zablokuje `Edit`/`Write` na chránenom priečinku. Na nastavenie takéhoto hooku použi skill **`/update-config`** (spravuje `settings.json`).

### D) Znalostná báza (tvoj moat)

Tvoje dáta sú tvoja konkurenčná výhoda. Nepýtaj len „sprav report“ — daj AI odkaz na referencie a označ, čo chýba, namiesto vymýšľania:

```text
Použi knowledge/reports/monthly-report-template.md ako štruktúru.
Použi knowledge/marketing/winning-hooks.md ako referenciu pre tón.
Ak niečo v týchto dokumentoch chýba, označ to ako nejasnosť, nevymýšľaj.
```

Na samotnú znalostnú bázu už máš nainštalované skilly — **použi `/llm-wiki`** (Karpathyho LLM Wiki vzor: ingest zdrojov, dopyty s citáciami) a **`/graphify`** (premena súborov na navigovateľný knowledge graph). Ak chceš len jednoduchú zložkovú štruktúru:

```text
/knowledge
  /company    positioning.md  ICP.md  offers.md
  /marketing  past-campaigns.md  winning-hooks.md  brand-voice.md
  /reports    monthly-report-template.md  examples.md
  /coding     architecture.md  conventions.md  deployment.md
  /personal   preferences.md  decision-principles.md
```

### E) Opakované postupy → skilly

Čokoľvek robíš opakovane (newsletter, mesačný report, code review, kontrola landing page, premena poznámok na akčný plán) sprav ako skill — handbook na konkrétnu úlohu. Na vytvorenie použi **`/skill-creator`**. Čím viac skill používaš, tým lepší bude — *najlepší spôsob, ako nájsť dieru v hadici, je pustiť cez ňu vodu.*

## Výstup

Po behu tohto skillu má projekt: hotový `CLAUDE.md`, jasné always/ask/never buckety, (voliteľne) hook na kritické súbory a odkaz na znalostnú bázu. Zmeny v `CLAUDE.md` a hookoch mi pred zápisom daj odsúhlasiť.
