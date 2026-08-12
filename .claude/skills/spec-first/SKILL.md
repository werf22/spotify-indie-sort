---
name: spec-first
description: "Use at the START of any larger or multi-step task to FIRST interview the user and pin down the real goal before doing anything — instead of guessing. Produces a tight spec and breaks the work into small agile checkpoints. Trigger whenever the user opens a non-trivial task ('sprav mi report/analýzu/plán/feature', 'pomôž mi s…'), jumps straight to a task without stating the goal, or types /spec-first. Bias strongly toward triggering: if the task could be done two different ways depending on intent, run this first."
---

# /spec-first — Vrstva 1: Spec

**Najprv ma vyspovedaj, potom rieš.** Toto je vstupný skill pred každou väčšou úlohou.

## Prečo to existuje

AI je ako *robotický knihovník*: skvelý v tom, čo sa dá zmerať, ale slepý voči tvojmu kontextu. Keď mu nedodáš svoje porozumenie vo forme špecifikácie, začne **hádať, robiť nesprávne predpoklady a tváriť sa sebaisto**. Jedna vec, ktorú za teba nikdy nerozhodne, je **cieľ** — to musí prísť od teba. Tento skill ten cieľ vytiahne von a premení na spec, podľa ktorého sa dá pracovať.

`„Sprav mi mesačný report“` = úloha.
`„Chcem zistiť, prečo klesli konverzie a ktoré 3 veci budúci mesiac zmeniť“` = cieľ.

## Postup

### Krok 1 — Vyspovedaj (NEZAČÍNAJ riešiť)

Nepúšťaj sa do riešenia, kým nie je jasné týchto 5 vecí. Polož ich ako otázky, počkaj na odpovede:

```text
Najprv ma vyspovedaj, aby sme presne identifikovali cieľ tejto úlohy.
Nepúšťaj sa do riešenia, kým nebude jasné:
1. aké rozhodnutie má výstup podporiť,
2. pre koho je výstup,
3. čo musí obsahovať,
4. čo tam určite nemá byť,
5. ako bude vyzerať dobrý výsledok.
```

Pýtaj sa cielene a po malých dávkach. Ak na niečo nevieš odpoveď ani po spovedi, **navrhni najpravdepodobnejší predpoklad a označ ho ako predpoklad** — nevymýšľaj fakty.

### Krok 2 — Napíš tesný spec

Keď máš odpovede, zhrň ich do krátkej, ale presnej špecifikácie a daj ju odsúhlasiť:

```text
- Cieľ (rozhodnutie, ktoré výstup podporuje)
- Publikum
- Vstupy
- Výstup (formát + štruktúra)
- Obmedzenia
- Predpoklady (explicitne označené)
- Čo NEBUDE súčasťou úlohy
```

### Krok 3 — Agilne, nie waterfall

Nerob obrovskú úlohu naraz. Rozbi ju na malé, samostatné kroky a po každom ukáž checkpoint na schválenie:

```text
Rozdeľ túto úlohu na malé, samostatné kroky.
Pre každý krok mi najprv ukáž návrh alebo checkpoint, ktorý môžem schváliť alebo upraviť.
Biasuj smerom k menším špecifikáciám, nie k veľkému jednorazovému výstupu.
```

### Krok 4 — Daj mi overiť kľúčové rozhodnutia

Pri rozhodnutiach, ktoré menia smer výstupu, ma výslovne nechaj potvrdiť — nech sa nič dôležité nestratí v tichom predpoklade.

## Pravidlo

Nezačni s prácou, kým nemáš odsúhlasený spec z Kroku 2. Keď je úloha hotová, prirodzene pokračuj cez **`/verify-output`** (Vrstva 2 — kontrola kvality).

> Môžeš outsourcovať premýšľanie, ale nemôžeš outsourcovať porozumenie.
