---
name: rugol-review
description: Revisión de código con criterio de staff engineer sobre los cambios sin commitear o el último commit. Busca bugs que llegarían a producción, complejidad innecesaria y ediciones que no venían al caso.
---

# /rugol-review

Idea tomada de la skill `/review` de gstack (MIT, ver NOTICE). Reescrita para
Rugol: acá no hay una persona mirando la terminal, así que el resultado tiene
que ser un informe legible solo, no un diálogo.

## Cuándo usarla
Antes de dar por terminado un cambio. Si el usuario dice "revisá", "está listo?"
o "encontrás algo raro", esto es lo que corresponde.

## Alcance
1. `git diff` para lo no commiteado. Si está vacío, `git diff HEAD~1`.
2. Si tampoco hay, preguntá qué revisar en vez de inventar un alcance.

## Qué buscar, en este orden

**1. Correctitud** — lo único que justifica bloquear.
Para cada hallazgo necesitás un escenario concreto: qué entrada, qué estado,
qué sale mal. Sin escenario reproducible no es un hallazgo, es una corazonada.
- Casos borde sin cubrir: vacío, None, cero, negativo, unicode, zona horaria.
- Errores tragados: `except: pass` que oculta un fallo real.
- Concurrencia: estado compartido, orden de escrituras, reintentos no idempotentes.
- Rutas de error que nunca se ejercitaron.

**2. Complejidad que no hacía falta**
- Abstracción con un solo uso.
- Bandera de configuración que nadie va a cambiar.
- Reescritura de algo que la librería ya hacía.

**3. Ediciones que no venían al caso**
Archivos tocados que no tienen que ver con el pedido. Son la principal fuente
de regresiones sorpresa: nadie las revisa porque nadie las pidió.

**4. Lo que falta**
- Un cambio de comportamiento sin test.
- Un mensaje de error nuevo que no dice cómo arreglar el problema.
- Documentación que quedó describiendo el comportamiento viejo.

## Formato del informe

Por hallazgo:
```
[correctitud|complejidad|fuera-de-alcance|falta] archivo:línea
Qué: una oración.
Cómo falla: entrada concreta → resultado equivocado.
Arreglo sugerido: una oración.
```

Cerrá con un veredicto de una línea: *listo para mergear* o *arreglar N cosas
primero*.

## Reglas
- Ordená por severidad, no por archivo.
- Si no encontrás nada, decilo en una línea. Un informe inflado con
  observaciones de estilo entrena a que te ignoren.
- No reescribas el código en el informe salvo que el arreglo sea de una línea.
