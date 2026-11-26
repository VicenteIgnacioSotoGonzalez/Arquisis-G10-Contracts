# E3-032, E3-034 y E3-053 — Contrato de eventos SSE (RF01), v1

Fecha de propuesta: 2026-11-21. API: `GET /events/stream`, `Accept: text/event-stream`.

## Autorización y alcance

- `Authorization: Bearer <access-token>` de Auth0; la misma verificación JWT de `/audit/*` (firma, issuer, audience, exp, sub).
- Sólo operadores autenticados ven los eventos de **KLD**; una lectura no permite emitir órdenes ni alterar estados.
- El backend exige el scope OAuth `read:events` por defecto. `SSE_REQUIRED_SCOPE` permite seleccionar otro scope.
- Un JWT inválido, vencido o ausente devuelve `401`. Identidad vacía, permiso insuficiente o acceso revocado devuelven `403`.
- La ruta autentica exclusivamente con el bearer del header `Authorization`. Usar `fetch()` con lectura incremental. Las cookies quedan fuera de la autenticación del feed.
- Mantener JWT y claves fuera de la URL y de la query string. El proxy dedicado rechaza peticiones con parámetros de consulta con `400`.
- Configurar en Master los orígenes exactos de la SPA en `CORS_ALLOWED_ORIGINS`, incluido esquema y puerto cuando corresponda. Nginx reenvía `OPTIONS` al middleware CORS. Enviar el preflight sin JWT, con `Origin`, `Access-Control-Request-Method: GET` y `Access-Control-Request-Headers: Authorization,Last-Event-ID` cuando se reanude. Un preflight permitido devuelve `200`, el origen exacto y los métodos y headers permitidos. Un origen ajeno recibe `400` en el preflight, sin `Access-Control-Allow-Origin`.

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
- Durante inactividad, Master envía comentarios `: heartbeat` aproximadamente cada 15 segundos. Los comentarios quedan fuera de la secuencia de IDs y del checkpoint.
- Master devuelve `401` o `403` antes de comenzar la respuesta. Tras el `200`, la expiración del JWT o la detección de revocación cierran la conexión. Reabrir con autorización vigente y enviar el último ID completamente procesado en `Last-Event-ID`.
- El cliente deduplica por el ID del frame y conserva el último que haya procesado por completo. Para reiniciar sin cursor tras un `400` o `409`, debe limpiar la vista del historial antes de volver a mostrarlo desde el comienzo.

## Origen HTTPS de E3-053

La IaC del backend declara una HTTP API v2 en AWS API Gateway. El modo `STREAM` está disponible para REST API con integraciones `HTTP_PROXY` o `AWS_PROXY`. El diseño de E3-053 usa un origen HTTPS dedicado en Nginx delante de Master cuando la puerta original no puede transmitir incrementalmente. [Modos de transferencia de AWS API Gateway](https://docs.aws.amazon.com/apigateway/latest/developerguide/response-transfer-mode.html)

El host se configura por ambiente con el valor confirmado en el despliegue. La ruta sigue siendo `GET /events/stream` con el mismo formato v1. El proxy dedicado desactiva buffering, caché y compresión y devuelve `Cache-Control: no-cache, no-store, no-transform`. Master conserva la autorización y el replay sin depender de la réplica que atienda la reconexión.

Coordinar con frontend que el panel pase la base HTTPS del feed a `openSseFeed({apiUrl})`. El servicio acepta esa opción y el panel de E3-052 hereda `VITE_API_URL`. Al habilitar el origen dedicado, conservar la base general para los demás endpoints. Verificar en staging, desde el origen desplegado de la SPA, el preflight, la llegada de dos eventos generados en momentos distintos por una misma conexión y la reconexión. La plantilla del backend tiene cobertura HTTPS local. La activación en staging y el dominio público quedan por confirmar.
