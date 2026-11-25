# E3-032 — Contrato de eventos SSE (RF01), v1

Fecha de propuesta: 2026-11-21. API: `GET /events/stream`, `Accept: text/event-stream`.

## Autorización y alcance

- `Authorization: Bearer <access-token>` de Auth0; la misma verificación JWT de `/audit/*` (firma, issuer, audience, exp, sub).
- Sólo operadores autenticados ven los eventos de **KLD**; una lectura no permite emitir órdenes ni alterar estados.
- Con `SSE_REQUIRED_SCOPE=read:events` configurado en el backend, también exige ese OAuth scope. El valor por defecto vacío preserva la autorización actual del módulo audit.
- Un JWT inválido o ausente: `401`. Identidad vacía o permiso insuficiente: `403`.
- Nunca enviar el JWT por URL o query string; `EventSource` nativo no permite Authorization, usar `fetch()` streaming.
- CORS: sólo orígenes configurados, no usar comodines irrestrictos. La configuración de API Gateway debe admitir además el header `Last-Event-ID` en las solicitudes CORS preflight (y `Authorization`).

## Formato

Respuesta HTTP exitosa:

```
HTTP/1.1 200 OK
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache, no-transform

id: 23
event: wallet
data: {"id":23,"type":"wallet","occurredAt":"2026-11-22T12:31:00Z","cycleId":"ciclo-v3-123","data":{"source":"INBOUND","messageType":"swap-settled","status":"PROCESSED"}}

: heartbeat

```

Todos los eventos poseen `id` entero, monotónico global y positivo; `type` entre `market|wallet|saga|alert`; `occurredAt` ISO-8601 UTC; `cycleId` cadena opaca o null; `data` objeto de sólo tres metadatos filtrados: `source`, `messageType`, `status`.

`source` es `INBOUND|OUTBOUND|RECONCILIATION`; `messageType` proviene de una lista blanca de tipos del protocolo y `SAGA_START`/`wallet-reconciliation`; `status` se limita a un conjunto explícito y el desconocido se presenta como `OTHER`.

No se incluyen `idpk`, `msgId`, `swapToken`, `Idempotency-Key`, `execution_input`, `last_error`, `raw_payload`, `payload`, JWT, claves AWS ni otros campos sensibles. Los mensajes de auditoría/outbox se transforman a notificaciones seguras; jamás se serializa la fila ORM o el JSONB original.

## Categorías

- `market`: `offer`, `offer-updated`, `offer-withdrawn`, `bid`, `bid-accepted`, `bid-rejected`, `trade-recorded`, `market-closed`, `status-statement`, `negotiation-report`.
- `wallet`: `swap-proposed`, `swap-settled`, `swap-rejected`, `swap-expired`, `swap-cancelled`, `transfer`; conciliación sin alerta.
- `saga`: registro/actualización de intención `SAGA_START` en outbox de destino `STEP_FUNCTIONS`.
- `alert`: mensajes con estado `FAILED|NACKED|DISCARDED`, `nack`, conciliación `MISMATCH|ERROR`.

Estos son **hechos persistidos**. `PUBLISHED` no equivale a aceptación comercial; `202` no equivale a `SETTLED` y `SAGA_START/STARTED` no implica saga finalizada. Las alarmas CloudWatch/New Relic y transiciones detalladas de ejecución se integrarán en tareas E3 posteriores cuando sus fuentes estén disponibles.

## Durabilidad, secuencia y reinicio

La tabla `sse_feed_events` registra una proyección pública generada mediante triggers transaccionales sobre `inbound_messages`, `outbound_messages` y `wallet_reconciliations`. Una fila `sse_feed_cursor` serializa la asignación de IDs mientras se confirma la transacción fuente. Un rollback revierte simultáneamente el ID y el evento. Una transacción que confirma después no puede generar un ID menor que uno ya visible.

No se realiza backfill automático de hechos previos a la migración: la secuencia comienza con eventos creados tras instalar el registro. No se debe truncar historial de eventos en producción sin una política explícita de retención y recuperación.

- `Last-Event-ID: 23` devuelve IDs mayores que 23 en orden ascendente; `id` identifica el evento mostrado, no la operación económica.
- Header ausente: comenzar desde 0 (todos los eventos retenidos).
- Cursor malformado: `400`; cursor mayor que el confirmado actual: `409`.
- Los comentarios `: heartbeat` no avanzan el cursor ni son eventos de negocio.
- Las conexiones se cierran en caso de desconexión del cliente o expiración del JWT, y deben reabrirse con un token vigente.
- Un cliente debe deduplicar por ID y conservar el último confirmado. El alcance E3-034 comprende validación integral de reconexión, retención e integración end-to-end.

## Advertencia de infraestructura

El despliegue público actual pasa por AWS API Gateway y necesita **confirmación independiente de soporte de streaming real** (tipo de API, integración, modo de transferencia, buffering y timeouts). La existencia de un `StreamingResponse` en FastAPI **no garantiza** SSE en producción. Validar con `curl -N` apuntando al dominio público antes de marcar E3-033 como desplegada.
