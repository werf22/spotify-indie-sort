---
name: modern-engineering
description: "The full 'do it right, not fast' method (Karpathy: spec → verifier → environment) for an important, high-stakes, or multi-step task. Chains it all: interview for the real goal → tight spec → agile checkpoints → up-front evaluation criteria → critic verification. Trigger when the user wants to do something properly/carefully, says 'spravme to poriadne / chcem to spraviť správne nie rýchlo / do it right', on a task where being wrong is costly, or on /modern-engineering. For a quick single task, /spec-first alone may be enough."
---

# /modern-engineering — celý postup (Spec → Verifier → Environment)

**„Chcem túto úlohu spraviť správne, nie rýchlo.“** Toto je hlavný vstupný bod pre dôležité úlohy. Spája tri vrstvy do jedného toku.

## Prečo to existuje

AI vie spraviť 80 % práce, ale ty musíš vedieť **čo** sa snažíš dosiahnuť, **prečo** na tom záleží a **podľa čoho** spoznáš, že výsledok je dobrý. Tri vrstvy stoja na sebe: spec dodá tvoje porozumenie, verifier ho ustráži, environment im dá kde žiť.

> Môžeš outsourcovať premýšľanie, ale nemôžeš outsourcovať porozumenie.

## Univerzálny prompt (jadro)

```text
Chcem túto úlohu spraviť správne, nie rýchlo.

Najprv ma vyspovedaj, aby sme identifikovali skutočný cieľ a rozhodnutie, ktoré má výstup podporiť.

Potom vytvor krátku, ale presnú špecifikáciu:
- cieľ,
- publikum,
- vstupy,
- výstup,
- obmedzenia,
- predpoklady,
- čo nebude súčasťou úlohy.

Rozdeľ prácu na malé checkpointy.

Pred samotnou prácou navrhni hodnotiace kritériá, podľa ktorých budeš výsledok kontrolovať.

Po dokončení sa prepni do role kritika a over výstup voči špecifikácii.
Označ slabé miesta, nejasnosti a predpoklady.
```

## Postup (čo reálne spravím)

1. **Spec (Vrstva 1).** Vyspovedám ťa a vytvorím tesnú špecifikáciu. Detailný postup a otázky → riaď sa skillom **`/spec-first`**. Bez odsúhlaseného specu nepokračujem.
2. **Checkpointy.** Rozdelím prácu na malé, samostatné kroky; po každom ukážem výsledok na schválenie (agile, nie waterfall).
3. **Kritériá vopred (Vrstva 2).** Ešte pred prácou navrhnem presné hodnotiace kritériá — čo znamená „dobré“.
4. **Práca po checkpointoch.** Postupujem, pri kľúčových rozhodnutiach si vyžiadam potvrdenie a označím predpoklady.
5. **Verifikácia (Vrstva 2).** Po dokončení sa prepnem do role kritika a overím výstup proti specu a kritériám; pri dôležitých veciach pridám externý signál (dáta, minulý dokument, log, test). Detail → skill **`/verify-output`**.

## Prostredie (Vrstva 3)

Ak túto rigoróznosť chceš mať natrvalo (a nie ju písať pri každej úlohe), nastav si prostredie cez **`/setup-environment`**: `CLAUDE.md`, guardraily always/ask/never, hooky na kritické súbory a znalostnú bázu (`/llm-wiki`, `/graphify`). Opakované úlohy sprav ako skill cez `/skill-creator`.

## Vzťah k ostatným skillom

- Rýchla úloha → stačí **`/spec-first`**.
- Treba len overiť hotový výstup → **`/verify-output`**.
- Nastavenie projektu/pravidiel → **`/setup-environment`**.
- Dôležitá, viac-kroková úloha od nuly po finál → **`/modern-engineering`** (tento skill).
