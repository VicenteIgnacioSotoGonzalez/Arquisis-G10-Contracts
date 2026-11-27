# E3-032, E3-034, E3-053 y E3-054 — Contrato de eventos SSE (RF01), v1

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

`source` admite `INBOUND`, `OUTBOUND`, `RECONCILIATION`, `SAGA` y `MONITORING`. `messageType` identifica un tipo permitido de protocolo o un código del feed. Para estados heredados desconocidos, el backend emite `OTHER`.

El payload excluye `swapId`, `idpk`, `msgId`, `swapToken`, `Idempotency-Key`, `execution_input`, `last_error`, `raw_payload`, `payload`, JWT, claves AWS ni otros campos sensibles. Los mensajes de auditoría/outbox se transforman a notificaciones seguras; jamás se serializa la fila ORM o el JSONB original.

## Categorías

- `market`: `offer`, `offer-updated`, `offer-withdrawn`, `bid`, `bid-accepted`, `bid-rejected`, `trade-recorded`, `market-closed`, `status-statement`, `negotiation-report`.
- `wallet`: `swap-proposed`, `swap-settled`, `swap-rejected`, `swap-expired`, `swap-cancelled`, `transfer`; conciliación sin alerta.
- `saga`: registro/actualización de intención `SAGA_START` en outbox de destino `STEP_FUNCTIONS`.
- `alert`: mensajes con estado `FAILED|NACKED|DISCARDED`, `nack`, conciliación `MISMATCH|ERROR`.

Estos son **hechos persistidos**. `PUBLISHED` no equivale a aceptación comercial; `202` no equivale a `SETTLED` y `SAGA_START/STARTED` no implica saga finalizada. E3-054 agrega las transiciones y alertas descritas abajo.

## Durabilidad, secuencia y reinicio

Los triggers de auditoría, outbox, conciliación y saga guardan candidatos en la transacción de origen. Un proyector publica los candidatos confirmados, asigna IDs contiguos y avanza el cursor en una sola transacción independiente. Los IDs siguen el orden confirmado de publicación. `occurredAt` indica el momento de captura u observación y puede retroceder dentro de ese orden.

La secuencia comienza con eventos creados tras instalar el registro. E3-054 agrega hechos al historial existente y conserva los IDs publicados. La versión actual conserva el historial indefinidamente. Los IDs son globales dentro del feed de KLD y compartidos entre réplicas.

- `Last-Event-ID: 23` devuelve IDs mayores que 23 en orden ascendente; `id` identifica el evento mostrado, no la operación económica.
- Con el header ausente, vacío o `0`, se reproduce todo el historial. El cursor usa decimal ASCII canónico y admite hasta `9223372036854775807`.
- Un cursor malformado devuelve `400`. Un cursor superior al último ID publicado devuelve `409`.
- Un hueco del historial o una falla de lectura devuelve `503` al iniciar el stream. Una conexión activa se cierra si la lectura deja de estar disponible.
- Durante inactividad, Master envía comentarios `: heartbeat` aproximadamente cada 15 segundos. Los comentarios quedan fuera de la secuencia de IDs y del checkpoint.
- Master devuelve `401` o `403` antes de comenzar la respuesta. Tras el `200`, la expiración del JWT o la detección de revocación cierran la conexión. Reabrir con autorización vigente y enviar el último ID completamente procesado en `Last-Event-ID`.
- El cliente deduplica por el ID del frame y conserva el último que haya procesado por completo. Para reiniciar sin cursor tras un `400` o `409`, debe limpiar la vista del historial antes de volver a mostrarlo desde el comienzo.


## Transiciones y alertas E3-054

Una transición usa `event: saga`, `data.source = SAGA` y `data.messageType = saga-transition`. Su `data.status` refleja `PENDING_START`, `RUNNING`, `WAITING`, `SETTLED`, `REJECTED`, `FAILED`, `COMPENSATED` o `TIMED_OUT`. El evento previo `SAGA_START` de origen `OUTBOUND` conserva el significado de sus estados.

Una alerta usa `event: alert`. `data.messageType` identifica la familia y `data.status` describe la observación. La severidad del sistema de monitoreo queda fuera del payload.

| Código | Origen | Estado |
| --- | --- | --- |
| `ledger-wallet-delta` | `RECONCILIATION` | `DIVERGENT` |
| `saga-stuck` | `SAGA` | `OPEN` |
| `outbox-aged` | `OUTBOUND` | `OPEN` |
| `wallet-slow` | `MONITORING` | `OPEN` |
| `consumer-lag` | `MONITORING` | `OPEN` |

`OPEN` representa una apertura observada. Las alertas de monitoreo ilustradas requieren condiciones verificadas y un importador operativo. Su `cycleId` es `null`. Los eventos de conciliación sin divergencia y las alertas previas de auditoría siguen disponibles.

```text
id: 24
event: saga
data: {"id":24,"type":"saga","occurredAt":"2026-11-22T12:31:00Z","cycleId":"ciclo-v3-123","data":{"source":"SAGA","messageType":"saga-transition","status":"WAITING"}}

id: 25
event: alert
data: {"id":25,"type":"alert","occurredAt":"2026-11-22T12:31:00Z","cycleId":null,"data":{"source":"MONITORING","messageType":"wallet-slow","status":"OPEN"}}

```

## Búsqueda autorizada por correlación

Enviar `POST /events/search` al mismo origen HTTPS que el feed con el bearer y `Content-Type: application/json`. El navegador usa preflight para `POST` con `Authorization` y `Content-Type`. El cuerpo admite exactamente un selector de coincidencia completa y sensible a mayúsculas, `cycleId`, `swapId` o `idpk`. El selector debe contener de 1 a 256 caracteres sin NUL. `after` es opcional y usa el mismo formato decimal que `Last-Event-ID`.

```json
{"cycleId":"ciclo-v3-123","after":"23"}
```

La respuesta `200` tiene `Cache-Control: no-store` y un objeto `events` con hasta 100 eventos en orden ascendente por el ID global. Los resultados filtrados pueden saltar IDs. Continuar con el último ID devuelto. Una búsqueda sin coincidencias o con un cursor futuro válido devuelve `{"events":[]}`.

El servidor resuelve `swapId` e `idpk` contra las filas fuente conservadas de saga, auditoría y outbox. Un evento anterior a la vinculación de un swap puede aparecer en resultados posteriores. Mantener los filtros en el cuerpo y fuera de URLs y logs. La respuesta muestra el evento público y omite las claves de búsqueda privadas.

La búsqueda usa el mismo permiso SSE y la misma comprobación de revocación que el stream. Devuelve `401` para credencial ausente, inválida o vencida, `403` para sujeto sin acceso y `503` si la consulta o autenticación no está disponible. El backend lee el JSON de la petición y devuelve `400` para un filtro o cursor inválido, incluido un cuerpo con más de un selector. Esta validación no emite `422`. El proxy dedicado devuelve `413` si el cuerpo supera 4 KiB.

## Compatibilidad de clientes

E3-054 conserva los nombres `market`, `wallet`, `saga` y `alert`, la forma JSON y la numeración de E3-052. El cliente E3-052 tiene una lista cerrada de fuentes. Debe admitir `SAGA` y `MONITORING` antes de activar las nuevas fuentes en un ambiente compartido. Una versión anterior puede omitir sus tramas y avanzar el cursor al procesar un evento posterior.

## Origen HTTPS de E3-053

La IaC del backend declara una HTTP API v2 en AWS API Gateway. El modo `STREAM` está disponible para REST API con integraciones `HTTP_PROXY` o `AWS_PROXY`. El diseño de E3-053 usa un origen HTTPS dedicado en Nginx delante de Master cuando la puerta original no puede transmitir incrementalmente. [Modos de transferencia de AWS API Gateway](https://docs.aws.amazon.com/apigateway/latest/developerguide/response-transfer-mode.html)

El host se configura por ambiente con el valor confirmado en el despliegue. La ruta sigue siendo `GET /events/stream` con el mismo formato v1. El proxy dedicado desactiva buffering, caché y compresión y devuelve `Cache-Control: no-cache, no-store, no-transform`. Master conserva la autorización y el replay sin depender de la réplica que atienda la reconexión.

Coordinar con frontend que el panel pase la base HTTPS del feed a `openSseFeed({apiUrl})`. El servicio acepta esa opción y el panel de E3-052 hereda `VITE_API_URL`. Al habilitar el origen dedicado, conservar la base general para los demás endpoints. Verificar en staging, desde el origen desplegado de la SPA, el preflight, la llegada de dos eventos generados en momentos distintos por una misma conexión y la reconexión. La plantilla del backend tiene cobertura HTTPS local. La activación en staging y el dominio público quedan por confirmar.
