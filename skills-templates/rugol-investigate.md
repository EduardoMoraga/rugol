---
name: rugol-investigate
description: Depuración por causa raíz con hipótesis explícitas y tope de intentos. Para cuando algo falla y no está claro por qué; evita el ciclo de parches a ciegas.
---

# /rugol-investigate

Idea tomada de la skill `/investigate` de gstack (MIT, ver NOTICE). El aporte
que se conserva es el tope de intentos: sin él, un agente prueba arreglos a
ciegas hasta agotar el contexto.

## Cuándo usarla
Algo falla y la causa no es obvia. Si la causa es obvia, arreglala y listo.

## Método

**Paso 1 — Reproducir antes de tocar nada.**
Necesitás un comando que falle de forma consistente. Si no podés reproducirlo,
eso es el hallazgo: decilo y pedí los datos que faltan. No arregles a ciegas.

**Paso 2 — Escribir tres hipótesis, ordenadas.**
Antes de cambiar una línea, anotá:
```
H1 (más probable): ... → cómo la descarto: ...
H2:                ... → cómo la descarto: ...
H3:                ... → cómo la descarto: ...
```
Escribirlas evita el sesgo de perseguir la primera idea.

**Paso 3 — Descartar, no confirmar.**
Buscá activamente la evidencia que MATA cada hipótesis. Es más rápido y no se
autoengaña. Usá logs, `git log -S`, `git bisect`, prints temporales.

**Paso 4 — Arreglar la causa, no el síntoma.**
Cuando quede una sola hipótesis en pie, arreglá eso. Si el arreglo es un
`try/except` alrededor del error, no encontraste la causa.

**Paso 5 — Verificar con el comando del paso 1.**
Y agregá un test que falle sin el arreglo. Sin eso el bug vuelve.

## El tope: tres intentos fallidos y pará

Si tres arreglos no resolvieron el problema, **detenete y reportá**:
- qué probaste y qué pasó en cada intento;
- qué hipótesis quedaron vivas;
- qué información te falta para decidir.

Seguir después del tercero es cuando un agente empieza a romper cosas que
funcionaban. Parar con un informe honesto vale más que un cuarto intento.

## Lo que no se hace
- No cambies dependencias ni versiones "por probar".
- No refactorices de paso: primero arreglá, después limpiá.
- No borres el test que falla para que pase la suite.
