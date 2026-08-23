---
name: rugol-assumptions
description: Saca los supuestos a la luz antes de construir. Seis preguntas que evitan construir lo correcto para el problema equivocado.
---

# /rugol-assumptions

Idea tomada de la skill `/office-hours` de gstack (MIT, ver NOTICE). Adaptada:
gstack la usa como conversación con un humano; acá, cuando corrés desatendido,
las respuestas que no tenés se declaran como supuestos explícitos y se sigue.

## Cuándo usarla
Antes de un cambio no trivial. Si el pedido es "cambiá este texto", saltala.

## Las seis preguntas

1. **¿Qué problema tiene la persona?** No la solución que pidió: el problema.
   Si no lo podés escribir en una oración, no lo entendiste.
2. **¿Cómo lo resuelve hoy?** Si ya tiene una forma, tu cambio compite con un
   hábito, no con la nada.
3. **¿Cómo sabremos que funcionó?** Una señal observable. "Queda mejor" no lo es.
4. **¿Qué es lo más chico que sirve?** La versión que se puede probar mañana.
5. **¿Qué se rompe si esto sale mal?** Si la respuesta es "nada", andá rápido.
   Si es "los datos del cliente", andá despacio.
6. **¿Qué estoy asumiendo sin haberlo verificado?** La más importante. Todo lo
   que no comprobaste va acá.

## Salida

Un bloque corto, antes de escribir código:

```
Problema:   ...
Hoy:        ...
Éxito se ve como: ...
Mínimo:     ...
Riesgo:     ...
Supuestos (SIN verificar):
  - ...
  - ...
```

Después construí el mínimo. Si un supuesto se puede verificar en menos de dos
minutos —leer un archivo, correr un comando, consultar el API— verificalo y
sacalo de la lista en vez de dejarlo.

## Regla
Si un supuesto es de los que invalidan todo el trabajo cuando son falsos, no
sigas: verificá ése primero, o preguntá.
