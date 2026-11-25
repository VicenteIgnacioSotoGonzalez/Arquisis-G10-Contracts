# E3-032 y E3-034 — Contrato de eventos SSE (RF01), v1

Fecha de propuesta: 2026-11-21. API: `GET /events/stream`, `Accept: text/event-stream`.

## Autorización y alcance

- Enviar `Authorization: Bearer <access-token>` en cada conexión. La API verifica el JWT de Auth0 como en `/audit/*` y exige un `sub` no vacío y un `exp` vigente para el stream.
- El feed de sólo lectura de **KLD** es compartido por los operadores autorizados. El mismo permiso cubre el historial y los eventos en vivo. El backend exige `read:events` en el claim OAuth `scope` por defecto. `SSE_REQUIRED_SCOPE` permite seleccionar otro scope. La revocación se comprueba por `sub` al abrir la conexión y durante la lectura.
- En navegador, usar `fetch()` con lectura incremental para enviar `Authorization` y `Last-Event-ID`. `EventSource` nativo carece de soporte para headers personalizados. Mantener el JWT fuera de la URL.
- En solicitudes entre orígenes, el preflight CORS debe permitir el origen configurado y los headers `Authorization` y `Last-Event-ID`.

## Formato

Ejemplo de reconexión:

```http
GET /events/stream HTTP/1.1
Authorization: Bearer <access-token>
Accept: text/event-stream
Last-Event-ID: 21
```

Respuesta HTTP y primeros frames:

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache, no-store, no-transform
X-Accel-Buffering: no

id: 22
event: market
data: {"id":22,"type":"market","occurredAt":"2026-11-22T12:30:00Z","cycleId":"ciclo-v3-123","data":{"source":"INBOUND","messageType":"offer","status":"PROCESSED"}}

id: 23
event: wallet
data: {"id":23,"type":"wallet","occurredAt":"2026-11-22T12:31:00Z","cycleId":"ciclo-v3-123","data":{"source":"INBOUND","messageType":"swap-settled","status":"PROCESSED"}}

id: 24
event: saga
data: {"id":24,"type":"saga","occurredAt":"2026-11-22T12:32:00Z","cycleId":"ciclo-v3-123","data":{"source":"OUTBOUND","messageType":"SAGA_START","status":"STARTED"}}

id: 25
event: alert
data: {"id":25,"type":"alert","occurredAt":"2026-11-22T12:33:00Z","cycleId":"ciclo-v3-123","data":{"source":"RECONCILIATION","messageType":"wallet-reconciliation","status":"MISMATCH"}}

: heartbeat

```

Cada frame termina con una línea vacía. La línea `id` es el cursor decimal, `event` indica la categoría y `data` contiene un objeto JSON. En ese objeto, `id` es el mismo entero positivo del frame y `type` coincide con `event`. `occurredAt` está en ISO-8601 UTC, `cycleId` es una cadena opaca o `null` y el objeto interno `data` contiene sólo `source`, `messageType` y `status`. Los comentarios `: heartbeat` mantienen abierta la conexión sin avanzar el cursor.

`source` es `INBOUND|OUTBOUND|RECONCILIATION`; `messageType` proviene de una lista blanca de tipos del protocolo y `SAGA_START`/`wallet-reconciliation`; `status` se limita a un conjunto explícito y el desconocido se presenta como `OTHER`.

No se incluyen `idpk`, `msgId`, `swapToken`, `Idempotency-Key`, `execution_input`, `last_error`, `raw_payload`, `payload`, JWT, claves AWS ni otros campos sensibles. Los mensajes de auditoría/outbox se transforman a notificaciones seguras; jamás se serializa la fila ORM o el JSONB original.

## Categorías

- `market`: `offer`, `offer-updated`, `offer-withdrawn`, `bid`, `bid-accepted`, `bid-rejected`, `trade-recorded`, `market-closed`, `status-statement`, `negotiation-report`.
- `wallet`: `swap-proposed`, `swap-settled`, `swap-rejected`, `swap-expired`, `swap-cancelled`, `transfer`; conciliación sin alerta.
- `saga`: registro/actualización de intención `SAGA_START` en outbox de destino `STEP_FUNCTIONS`.
- `alert`: mensajes con estado `FAILED|NACKED|DISCARDED`, `nack`, conciliación `MISMATCH|ERROR`.

El feed muestra hechos persistidos. `PUBLISHED` confirma la publicación y `SAGA_START/STARTED` el inicio de la ejecución. Para Wallet, `202` confirma recepción de una solicitud. Los hechos terminales del swap se observan como `swap-settled`, `swap-rejected`, `swap-expired` o `swap-cancelled` según el resultado. Los eventos terminales de negocio se entregan como cualquier otro frame y el stream sigue abierto.

## Durabilidad, secuencia y reinicio

Los triggers de auditoría, outbox y conciliación guardan candidatos en la transacción de origen. Un proyector publica los candidatos confirmados, asigna IDs contiguos y avanza el cursor en una sola transacción independiente. Los IDs siguen el orden confirmado de publicación. `occurredAt` indica el momento de captura y puede retroceder dentro de ese orden.

La secuencia comienza con eventos creados tras instalar el registro. El replay es exclusivo (`id > cursor`) y ascendente, seguido por los eventos nuevos según se publican. Con `Last-Event-ID: 23`, el primer evento del ejemplo sería el 24. Si el cursor coincide con el último ID publicado, la conexión espera publicaciones nuevas.

El cursor acepta decimal ASCII canónico entre `0` y `9223372036854775807`, sin signo, espacios ni ceros iniciales. El header ausente, vacío o con `0` inicia desde el comienzo del historial. El cliente deduplica por ID y guarda el último frame procesado por completo. Conviene conservar el valor textual de la línea `id` para evitar pérdida de precisión en JavaScript.

Esta versión conserva todo el historial publicado, sin TTL ni código de cursor expirado. El replay requiere que exista el registro de un cursor positivo ya alcanzado y que los IDs posteriores sean contiguos. Si falta un registro al abrir, la API responde `503`. Si detecta el problema durante el stream, cierra la conexión.

## Errores, cierre y reintentos

| HTTP antes de abrir | Condición | Comportamiento del cliente |
| --- | --- | --- |
| `400` | Cursor malformado o fuera de rango (`Invalid Last-Event-ID`). | Corregir el cursor. |
| `401` | JWT ausente, inválido o vencido. | Obtener autorización vigente y conservar el último ID procesado. |
| `403` | Identidad vacía, scope insuficiente o acceso revocado. | Detener reintentos hasta recuperar el acceso. |
| `409` | Cursor adelantado al último ID publicado (`SSE cursor is ahead of the server`). | Verificar que el cursor pertenezca al historial del nodo consultado. |
| `422` | Error general de validación de la solicitud declarado por FastAPI (`HTTPValidationError`). | Corregir la solicitud según `detail`. Un valor inválido de `Last-Event-ID` se maneja con `400`. |
| `503` | Historial incompleto, lectura indisponible o verificación de autenticación indisponible. | Reintentar con espera creciente y el mismo cursor. Si el hueco persiste, la recuperación requiere restaurar el historial. |

Después de `200`, la expiración del JWT, la revocación o una falla de lectura cierran la conexión sin frame terminal ni nuevo estado HTTP. Ante un corte transitorio, reabrir con backoff, un JWT vigente y el último ID procesado. El servidor no envía un campo SSE `retry`. Si después de un `400` o `409` se decide reproducir desde el inicio, limpiar primero la vista y su cursor local para evitar duplicados visibles.

## Transporte e intermediarios

OpenAPI describe la respuesta como texto `text/event-stream` y muestra el formato de los frames. El cliente debe leer y decodificar el cuerpo UTF-8 de forma incremental y tolerar frames repartidos entre varias lecturas. Las herramientas y clientes generados pueden almacenar la respuesta completa en memoria. Para que el feed funcione a través de API Gateway y los proxies, la integración debe reenviar los bytes sin buffering y contar con timeouts compatibles con una conexión larga. `X-Accel-Buffering: no` solicita desactivar el buffering en los proxies compatibles. La entrega incremental a través del gateway se comprueba por separado en el ambiente correspondiente.
