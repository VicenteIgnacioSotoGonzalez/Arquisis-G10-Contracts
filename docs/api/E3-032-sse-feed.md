# E3-032 y E3-034 — Contrato de eventos SSE (RF01), v1

Fecha de propuesta: 2026-11-21. API: `GET /events/stream`, `Accept: text/event-stream`.

## Autorización y alcance

- `Authorization: Bearer <access-token>` de Auth0; la misma verificación JWT de `/audit/*` (firma, issuer, audience, exp, sub).
- Sólo operadores autenticados ven los eventos de **KLD**; una lectura no permite emitir órdenes ni alterar estados.
- El backend exige el scope OAuth `read:events` por defecto. `SSE_REQUIRED_SCOPE` permite seleccionar otro scope.
- Un JWT inválido, vencido o ausente devuelve `401`. Identidad vacía, permiso insuficiente o acceso revocado devuelven `403`.
- Nunca enviar el JWT por URL o query string; `EventSource` nativo no permite Authorization, usar `fetch()` streaming.
- CORS: sólo orígenes configurados, no usar comodines irrestrictos. La configuración de API Gateway debe admitir además el header `Last-Event-ID` en las solicitudes CORS preflight (y `Authorization`).

## Formato

Respuesta HTTP exitosa:

```
HTTP/1.1 200 OK
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache, no-store, no-transform

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

Los triggers de auditoría, outbox y conciliación guardan candidatos en la transacción de origen. Un proyector publica los candidatos confirmados, asigna IDs contiguos y avanza el cursor en una sola transacción independiente. Los IDs siguen el orden confirmado de publicación. `occurredAt` indica el momento de captura y puede retroceder dentro de ese orden.

La secuencia comienza con eventos creados tras instalar el registro. Esta versión conserva el historial publicado indefinidamente.

- `Last-Event-ID: 23` devuelve IDs mayores que 23 en orden ascendente; `id` identifica el evento mostrado, no la operación económica.
- Con el header ausente, vacío o `0`, se reproduce todo el historial. El cursor usa decimal ASCII canónico y admite hasta `9223372036854775807`.
- Un cursor malformado devuelve `400`. Un cursor superior al último ID publicado devuelve `409`.
- Un hueco del historial o una falla de lectura devuelve `503` al iniciar el stream. Una conexión activa se cierra si la lectura deja de estar disponible.
- Los comentarios `: heartbeat` no avanzan el cursor ni son eventos de negocio.
- Las conexiones se cierran al expirar el JWT o revocarse el acceso. El cliente puede reabrirlas cuando cuente con autorización vigente.
- El cliente deduplica por el ID del frame y conserva el último que haya procesado por completo. Para reiniciar sin cursor tras un `400` o `409`, debe limpiar la vista del historial antes de volver a mostrarlo desde el comienzo.

## Advertencia de infraestructura

El despliegue público actual pasa por AWS API Gateway y necesita **confirmación independiente de soporte de streaming real** (tipo de API, integración, modo de transferencia, buffering y timeouts). La existencia de un `StreamingResponse` en FastAPI **no garantiza** SSE en producción. Validar con `curl -N` apuntando al dominio público antes de marcar E3-033 como desplegada.
