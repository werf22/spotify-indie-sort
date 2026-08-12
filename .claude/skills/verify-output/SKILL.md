---
name: verify-output
description: "Use to define HOW an output will be judged BEFORE building it, then verify it afterward — instead of trusting that something 'looks good'. Sets precise evaluation criteria up front, runs a critic pass against the spec, and pulls external signal (real data, past documents, logs, tests). Trigger before finalizing any important deliverable, when the user says 'sprav to kvalitne / over to / make sure it's right', when checking a deployment/report/document, or on /verify-output. Bias toward triggering whenever the cost of being wrong is non-trivial."
---

# /verify-output — Vrstva 2: Verifier

**Vopred urči, ako sa bude výsledok kontrolovať. Potom to skutočne over.**

## Prečo to existuje

AI často vyrobí niečo, čo *vyzerá dobre*, ale nie je to správne. Je to robotický knihovník: keď mu v „knižnici“ chýba kniha, nevie o tom — odpovie sebaisto a nesprávne. Jediná páka, ktorú reálne máš, nie je „skús to lepšie“ ani prosenie, ale **verifikácia**. Dobrá spätná väzba zdvihne kvalitu výstupu 2–3×.

## Postup

### Krok 1 — Hodnotiace kritériá VOPRED

Skôr než sa čokoľvek vyrobí, definuj presne, čo znamená „dobré“. Konkrétne, nie „sprav to kvalitne“:

```text
Predtým, ako začneš, navrhni presné hodnotiace kritériá.
Výstup musí byť overený podľa týchto bodov:
- či odpovedá na hlavný cieľ,
- či nepoužíva neoverené predpoklady,
- či má jasnú štruktúru,
- či obsahuje konkrétne odporúčania,
- či sú riziká a nejasnosti explicitne pomenované.
```

### Krok 2 — Druhé kolo: rola kritika

Po dokončení sa AI prepne do role kritika a hodnotí výstup proti pôvodnému specu a kritériám. Ideálne to spraví **druhý model / druhá perspektíva** (nový kontext, prípadne iný nástroj):

```text
Po dokončení výstupu sa prepni do role kritika.
Skontroluj výstup proti pôvodnej špecifikácii a hodnotiacim kritériám.
Vypíš:
1. čo je dobré,
2. čo je slabé,
3. čo môže byť nesprávny predpoklad,
4. čo treba upraviť pred finálnou verziou.
```

V Claude Code môžeš na nezávislú kontrolu spustiť subagenta (`Agent` / `Explore`) alebo iný model — nech to nehodnotí ten istý kontext, čo to vyrobil.

### Krok 3 — Pridaj externý signál

Pri dôležitých veciach sa nespoliehaj na „myslím si, že je to správne“. Over to voči realite — zdroju, dátam, existujúcemu dokumentu, logu alebo testu:

```text
Porovnaj tento výstup s priloženým minulomesačným reportom a zachovaj rovnakú štruktúru.
```

```text
Nespokoj sa s tvrdením, že deployment prešiel.
Navrhni konkrétny spôsob, ako to overiť cez logy, endpoint alebo test.
```

## Pravidlo

Nehlás „hotovo / overené“, ak to reálne neprešlo Krokom 2 a (pri dôležitých veciach) Krokom 3. Ak overenie zlyhá, povedz to s dôkazom — nezakrývaj to.
