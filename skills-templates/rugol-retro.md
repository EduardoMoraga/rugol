---
name: rugol-retro
description: Retrospectiva sobre los datos reales de Rugol — corridas, costos, fallos y agentes de la última semana. Sale del API, no de la memoria.
---

# /rugol-retro

Inspirada en la skill `/retro` de gstack (MIT, ver NOTICE), pero con una
diferencia que es toda la ventaja de Rugol: gstack mira commits de git; acá
mirás **la operación de tu propia flota**, que Rugol ya tiene registrada.

## Regla número uno

Todos los números salen del API. Si no viste una respuesta 2xx en este turno,
no tenés el dato — decilo, no lo estimes.

```bash
curl -s http://127.0.0.1:8000/api/health/full
curl -s "http://127.0.0.1:8000/api/runs?limit=200"
curl -s http://127.0.0.1:8000/api/agents
curl -s http://127.0.0.1:8000/api/schedules
```

## Qué mirar

**1. Volumen y costo**
Corridas de los últimos 7 días, costo total, y el desglose por agente.
La pregunta útil no es "cuánto gasté" sino **"qué agente gasta sin devolver"**.

**2. Fallos**
- Tasa de fallo por agente. Uno con más del 20% está mal configurado, no con
  mala suerte.
- Distinguí `failed` de `interrupted`: lo segundo es un corte de la máquina,
  no un problema del agente.
- Errores repetidos: el mismo mensaje tres veces es un bug, no un evento.

**3. Schedules que no sirven**
Un schedule cuya salida nadie leyó nunca es costo puro. Cruzá las corridas
por horario contra si hubo alguna interacción después.

**4. Agentes muertos**
Los que no corrieron en la semana. O les falta un disparador, o no hacían falta.

## Formato

```
Semana del <fecha> al <fecha>

Operación
  corridas: N   ·  fallidas: N (X%)  ·  interrumpidas: N  ·  costo: US$ X

Lo que anduvo
  - ...

Lo que hay que arreglar (con el dato que lo respalda)
  - <agente>: 4 de 9 corridas fallaron con "<error>" → <acción concreta>

Para desactivar
  - <schedule o agente>: <por qué>
```

Cerrá con **una** acción para la semana que entra. Una, no cinco: una lista de
cinco no se hace.

## Reglas
- Sin datos del API, no hay retro. Decilo y pará.
- Nada de "mejorar la eficiencia": cada acción tiene que nombrar un agente, un
  schedule o un archivo.
