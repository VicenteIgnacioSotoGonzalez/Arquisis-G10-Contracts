# Arquisis-G10-Contracts

Este repo tiene los contratos utilizados por los componentes del sistema para tener una definición común de los mensajes del protocolo y, posteriormente, de la API HTTP del backend.

Este repo responde al requisito **RDOC04** de la E1, que pide un repositorio de contratos a nivel de organización que contenga los schemas de los mensajes de la mecánica y la especificación OpenAPI de la API propia.

## Contenido

```text
.
├── docs/schemas/
│   └── v2/
│       ├── common.schema.json
│       ├── ack.schema.json
│       ├── nack.schema.json
│       ├── error.schema.json
│       ├── request.schema.json
│       ├── status-statement.schema.json
│       ├── transfer.schema.json
│       ├── demand-statement.schema.json
│       ├── negotiation-proposal.schema.json
│       ├── give.schema.json
│       ├── take.schema.json
│       ├── negotiation-report.schema.json
│       └── distance-table.schema.json
│
├── docs/examples/
│   └── v2/
│       └── valid/
│           ├── ack-city.json
│           ├── demand-statement.json
│           ├── demand-statement-negative.json
│           ├── distance-table.json
│           ├── error-over-capacity.json
│           ├── give.json
│           ├── nack.json
│           ├── negotiation-proposal-give.json
│           ├── negotiation-proposal-take.json
│           ├── negotiation-report.json
│           ├── request.json
│           ├── status-statement.json
│           ├── take.json
│           ├── transfer.json
│           └── transfer-payment.json
│
└── docs/openapi/
    └── openapi.yaml
```

- [`docs/schemas/v2/`](docs/schemas/v2/): Schemas JSON de los mensajes del protocolo E1.
- [`docs/examples/v2/valid/`](docs/examples/v2/valid/): Ejemplos de mensajes válidos utilizados para probar los schemas.
- [`docs/openapi/openapi.yaml`](docs/openapi/openapi.yaml): Especificación OpenAPI de la API HTTP pública del backend.

## OpenAPI

La especificación de la API HTTP pública del backend se encuentra en:

[`docs/openapi/openapi.yaml`](docs/openapi/openapi.yaml)

Este contrato documenta la interfaz utilizada por el frontend para:

- consultar ciclos
- consultar conectividad
- consultar y crear negociaciones
- consultar anomalías de mensajes.

Las rutas internas utilizadas por `connector` y workers no forman parte de este contrato público.

La autenticación de los endpoints protegidos utiliza access tokens JWT emitidos por Auth0 mediante el esquema:

```text
Authorization: Bearer <token>
```

Los contratos de `docs/schemas/v2/` y los ejemplos de `docs/examples/v2/valid/` corresponden al protocolo de mensajería entre los componentes del sistema, mientras que `docs/openapi/openapi.yaml` describe la API HTTP consumida por el frontend.

## API pública desplegada

La implementación productiva de la API descrita por este contrato se encuentra disponible en:

```text
https://api.energyshark-g10.tech
```

El tráfico público llega al backend mediante AWS API Gateway.

El flujo general es:

```text
Frontend
   ↓
AWS API Gateway
   ↓
API pública EnergyShark
   ↓
Backend
```

La infraestructura específica de despliegue se documenta en los repositorios correspondientes.

---

## Autenticación

Las operaciones protegidas de la API utilizan access tokens JWT emitidos por Auth0.

El cliente envía el token mediante:

```http
Authorization: Bearer <access_token>
```

El audience utilizado por la API es:

```text
https://arquisis-e1-api/
```

Actualmente las operaciones de negociaciones son las que requieren autenticación:

```text
GET  /negotiations
GET  /negotiations/{negotiation_id}
POST /negotiations
```

La definición OpenAPI debe indicar mediante su `securityScheme` qué operaciones requieren Bearer JWT.

La validación efectiva del JWT y la configuración del authorizer pertenecen a la infraestructura/backend y no se implementan en este repositorio.

---

## Schema común

El archivo [`common.schema.json`](docs/schemas/v2/common.schema.json) contiene definiciones reutilizadas por los demás contratos.

Entre ellas se encuentran:

### UUID

```json
{
  "type": "string",
  "format": "uuid"
}
```

Se utiliza para validar campos como:

- `idpk`
- `msgId`
- `data.target`
- `data.becauseOf`

### Timestamp

Los timestamps se validan utilizando el formato `date-time`.

Ejemplo:

```json
"timestamp": "2026-09-09T03:00:00Z"
```

### City code

Los códigos de ciudades permitidos por la E1 están definidos como un `enum`.

### Base envelope

`baseEnvelope` exige:

```text
idpk
msgId
type
timestamp
```

A partir de este envelope se construyen dos variantes principales.

### City envelope

Un mensaje emitido por una ciudad debe incluir:

```json
"cityId": "COR"
```

### Central envelope

Un mensaje emitido por la central debe incluir:

```json
"sender": "central"
```

---

# Schemas implementados

## status-statement

Schema:

[`docs/schemas/v2/status-statement.schema.json`](docs/schemas/v2/status-statement.schema.json)

Ejemplo:

[`docs/examples/v2/valid/status-statement.json`](docs/examples/v2/valid/status-statement.json)

Representa el estado energético informado por la central para un ciclo.

Se estandarizaron los campos:

```text
cycleId
data.energy.generationCapacity
data.energy.consumption
data.energy.generationCost
data.validUntil
```

El mensaje hereda de `centralEnvelope`, debido a que es emitido por la central.

---

## transfer

Schema:

[`docs/schemas/v2/transfer.schema.json`](docs/schemas/v2/transfer.schema.json)

Ejemplos:

- [`docs/examples/v2/valid/transfer.json`](docs/examples/v2/valid/transfer.json)
- [`docs/examples/v2/valid/transfer-payment.json`](docs/examples/v2/valid/transfer-payment.json)

El protocolo utiliza `transfer` en varios contextos.

### Transferencia desde la central

Ejemplo:

```json
{
  "data": {
    "quantity": 50000
  }
}
```

Puede representar, por ejemplo, los fondos entregados por la central.

### Pago de una negociación

Un transfer asociado a una confirmación puede incluir:

```json
{
  "data": {
    "becauseOf": "uuid",
    "quantity": 435160
  }
}
```

`becauseOf` permite relacionar el pago con el mensaje de confirmación que lo originó.

Por esto, el schema permite un envelope emitido por la central y uno emitido por una ciudad.

---

## demand-statement

Schema:

[`docs/schemas/v2/demand-statement.schema.json`](docs/schemas/v2/demand-statement.schema.json)

Ejemplos:

- [`docs/examples/v2/valid/demand-statement.json`](docs/examples/v2/valid/demand-statement.json)
- [`docs/examples/v2/valid/demand-statement-negative.json`](docs/examples/v2/valid/demand-statement-negative.json)

Se estandariza:

```text
cycleId
data.balance.quantity
data.balance.valuePerKwh
```

El enunciado dice expresamente que `quantity` puede ser tanto positiva como negativa.

Por ello el schema define:

```json
"quantity": {
  "type": "number"
}
```

---

## negotiation-proposal

Schema:

[`docs/schemas/v2/negotiation-proposal.schema.json`](docs/schemas/v2/negotiation-proposal.schema.json)

Ejemplos:

- [`docs/examples/v2/valid/negotiation-proposal-take.json`](docs/examples/v2/valid/negotiation-proposal-take.json)
- [`docs/examples/v2/valid/negotiation-proposal-give.json`](docs/examples/v2/valid/negotiation-proposal-give.json)

Las propuestas voluntarias contienen:

```text
cycleId
data.direction
data.quantity
data.pricePerEnergy
```

`direction` se restringe a:

```json
[
  "take",
  "give"
]
```

La cantidad se exige mayor que cero.

---

## give

Schema:

[`docs/schemas/v2/give.schema.json`](docs/schemas/v2/give.schema.json)

Ejemplo:

[`docs/examples/v2/valid/give.json`](docs/examples/v2/valid/give.json)

Representa una confirmación de una operación de salida de energía.

Contiene:

```text
cycleId
data.target
data.energy
data.pricePerEnergy
```

`target` referencia mediante UUID el `msgId` de la propuesta original.

---

## take

Schema:

[`docs/schemas/v2/take.schema.json`](docs/schemas/v2/take.schema.json)

Ejemplo:

[`docs/examples/v2/valid/take.json`](docs/examples/v2/valid/take.json)

Representa una confirmación de una operación de entrada de energía.

Al igual que `give`, contiene:

```text
cycleId
data.target
data.energy
data.pricePerEnergy
```

---

## negotiation-report

Schema:

[`docs/schemas/v2/negotiation-report.schema.json`](docs/schemas/v2/negotiation-report.schema.json)

Ejemplo:

[`docs/examples/v2/valid/negotiation-report.json`](docs/examples/v2/valid/negotiation-report.json)

Corresponde al reporte enviado por la ciudad a la central al cierre de la ventana de negociación.

Se estandarizan:

```text
cycleId
data.budgetBalance
data.energyBalance
```

El enunciado permite estados negativos, y eso se permite en estos escenarios.

---

## request

Schema:

[`docs/schemas/v2/request.schema.json`](docs/schemas/v2/request.schema.json)

Ejemplo:

[`docs/examples/v2/valid/request.json`](docs/examples/v2/valid/request.json)

Permite solicitar directamente información emitida por la central.

Su contenido tiene la forma:

```json
{
  "data": {
    "ask": "status-statement"
  }
}
```

Se entregan como ejemplos `status-statement` y `distance-table`, pero no se especifica una lista de valores posibles. Por eso, `ask` se mantiene como un string no vacío en vez de restringirlo mediante un `enum` explícito.

---

# ACK, NACK y error

Se diferencia entre:

- recepción correcta
- rechazo del mensaje
- rechazo de una operación válida.

---

## ACK

Schema:

[`docs/schemas/v2/ack.schema.json`](docs/schemas/v2/ack.schema.json)

Ejemplo:

[`docs/examples/v2/valid/ack-city.json`](docs/examples/v2/valid/ack-city.json)

Un ACK contiene:

```json
{
  "type": "ack",
  "data": {
    "target": "uuid"
  }
}
```

`target` corresponde al `msgId` del mensaje que está siendo reconocido. 

El schema permite que un ACK sea emitido tanto por una ciudad como por la central.

---

## NACK

Schema:

[`docs/schemas/v2/nack.schema.json`](docs/schemas/v2/nack.schema.json)

Ejemplo:

[`docs/examples/v2/valid/nack.json`](docs/examples/v2/valid/nack.json)

Un NACK representa el rechazo de un mensaje que no cumple el protocolo.

El enunciado define las siguientes combinaciones o códigos:

| reason | code |
|---|---:|
| `MALFORMED_MESSAGE` | 422 |
| `UNKNOWN_TYPE` | 400 |
| `IDPK_EQUALS_MSGID` | 422 |
| `IDENTITY_MISMATCH` | 403 |

Se valida además que la combinación entre ambos sea correcta, en el sentido de que el reason y code coincidan.

Por ejemplo:

```json
{
  "reason": "UNKNOWN_TYPE",
  "code": 400
}
```

es válido, mientras que:

```json
{
  "reason": "UNKNOWN_TYPE",
  "code": 422
}
```

no.

Dentro de `data` se estandarizan:

```text
target
message
cycleId (opcional)
```

---

## Error

Schema:

[`docs/schemas/v2/error.schema.json`](docs/schemas/v2/error.schema.json)

Ejemplo:

[`docs/examples/v2/valid/error-over-capacity.json`](docs/examples/v2/valid/error-over-capacity.json)

Un `error` es diferente de un NACK.

A diferencia de una NACK, un `error` indica que el mensaje fue recibido y entendido, pero la operación solicitada no puede ejecutarse.

Se modelaron las razones definidas:

| reason | code |
|---|---:|
| `CYCLE_UNKNOWN` | 404 |
| `CYCLE_EXPIRED` | 410 |
| `PRICE_ABOVE_CAP` | 422 |
| `OVER_CAPACITY` | 409 |

Además:

- `PRICE_ABOVE_CAP` requiere `data.cap`.
- `OVER_CAPACITY` requiere `data.spare`.

Ejemplo:

```json
{
  "reason": "OVER_CAPACITY",
  "code": 409,
  "data": {
    "target": "uuid",
    "message": "give excede la capacidad vendible restante",
    "spare": 320
  }
}
```

---

## distance-table

Schema:

[`docs/schemas/v2/distance-table.schema.json`](docs/schemas/v2/distance-table.schema.json)

Ejemplo:

[`docs/examples/v2/valid/distance-table.json`](docs/examples/v2/valid/distance-table.json)

Cada destino de la tabla contiene:

```text
distance
transportCost
enabled
```

Por ejemplo:

```json
{
  "HGW": {
    "distance": 62763183,
    "transportCost": 0.0034,
    "enabled": true
  }
}
```

### Inconsistencias de distance-table

Existe una inconsistencia entre la regla del protocolo y el ejemplo de `distance-table`. La regla establece que un mensaje de la central debe utilizar:

```json
"sender": "central"
```

y no `cityId`.

Sin embargo, el ejemplo de `distance-table` del enunciado muestra:

```json
"cityId": "COR",
"type": "distance-table"
```

La versión anterior aceptaba ambas representaciones. **Actualización 2026-10-07:** la especificación v2 transcrita exige `sender: "central"`; schema, ejemplo y connector requieren esa identidad. La evidencia productiva posterior confirma que cityId null y cycleId deben tolerarse; el schema de distance-table lo permite. Esta decisión reemplaza la compatibilidad anterior.

---

### Inconsistencia sobre PRICE_ABOVE_CAP

La definición de errores clasifica `PRICE_ABOVE_CAP` como un mensaje de tipo `error` con código `422`. Sin embargo, después el ejemplo de este caso utiliza `"type": "nack"`. Para este contrato se siguió la definición general del protocolo, por lo que `PRICE_ABOVE_CAP` se modela como `error`.

# Prueba y validación de los schemas

Los contratos fueron probados utilizando `check-jsonschema`. La herramienta fue ejecutada dentro de un entorno virtual de Python.

## Crear el entorno virtual

Desde la raíz del repositorio:

```bash
python3 -m venv .venv
```

Activarlo:

```bash
source .venv/bin/activate
```

## Instalar el validador

Con el entorno virtual activo, se hace:

```bash
pip install check-jsonschema
```
## Validaciones ejecutadas

Se probaron los siguientes pares:

```bash
check-jsonschema \
  --schemafile docs/schemas/v2/status-statement.schema.json \
  docs/examples/v2/valid/status-statement.json

check-jsonschema \
  --schemafile docs/schemas/v2/transfer.schema.json \
  docs/examples/v2/valid/transfer.json

check-jsonschema \
  --schemafile docs/schemas/v2/transfer.schema.json \
  docs/examples/v2/valid/transfer-payment.json

check-jsonschema \
  --schemafile docs/schemas/v2/demand-statement.schema.json \
  docs/examples/v2/valid/demand-statement.json

check-jsonschema \
  --schemafile docs/schemas/v2/demand-statement.schema.json \
  docs/examples/v2/valid/demand-statement-negative.json

check-jsonschema \
  --schemafile docs/schemas/v2/negotiation-proposal.schema.json \
  docs/examples/v2/valid/negotiation-proposal-take.json

check-jsonschema \
  --schemafile docs/schemas/v2/negotiation-proposal.schema.json \
  docs/examples/v2/valid/negotiation-proposal-give.json

check-jsonschema \
  --schemafile docs/schemas/v2/give.schema.json \
  docs/examples/v2/valid/give.json

check-jsonschema \
  --schemafile docs/schemas/v2/take.schema.json \
  docs/examples/v2/valid/take.json

check-jsonschema \
  --schemafile docs/schemas/v2/negotiation-report.schema.json \
  docs/examples/v2/valid/negotiation-report.json

check-jsonschema \
  --schemafile docs/schemas/v2/request.schema.json \
  docs/examples/v2/valid/request.json

check-jsonschema \
  --schemafile docs/schemas/v2/ack.schema.json \
  docs/examples/v2/valid/ack-city.json

check-jsonschema \
  --schemafile docs/schemas/v2/nack.schema.json \
  docs/examples/v2/valid/nack.json

check-jsonschema \
  --schemafile docs/schemas/v2/error.schema.json \
  docs/examples/v2/valid/error-over-capacity.json

check-jsonschema \
  --schemafile docs/schemas/v2/distance-table.schema.json \
  docs/examples/v2/valid/distance-table.json
```

Además de probar ejemplos que se consideran correctos, se hicieron pruebas negativas para comprobar que los schemas pudiesen rechazar mensajes que no cumplen el contrato. Por dar un ejemplo, se eliminó temporalmente `cycleId` de un `status-statement` y la validación falló indicando que se trataba de una propiedad obligatoria. También se probó un `msgId` con formato UUID inválido, y `check-jsonschema` lo rechazó.

## Compatibilidad E1 v2 — 2026-10-07

- `request` no incluye cycleId; ask sigue siendo string abierto.
- `distance-table` exige sender central y admite cityId ausente/null y cycleId opcional. El ejemplo reproduce la metadata productiva informada, con UUID y distancias ilustrativos. La excepción queda en su schema, sin modificar otros envelopes.
- Los reportes requieren cycleId y cierre de un ciclo abierto por central. Retry conserva idpk; corrección usa ids nuevos. REPORT_TOO_EARLY acepta 422/425 y exige opensAt; CYCLE_EXPIRED es terminal.
- PRICE_ABOVE_CAP se conserva como error 422, pese al ejemplo. penalty permanece opcional/opaco y no debe descontarse nuevamente.
- OpenAPI incorpora historial/estado de reportes, negotiationOpen/validUntil y describe BUDGET_CARRYOVER. PUBLISHED y sentAt acreditan transporte, no aceptación.
- AMQP user_id, idpk distinto de msgId, correlación, idempotencia y ventanas se comprueban en ejecución; JSON Schema individual no expresa esas invariantes.

Validación de schemas, ejemplos válidos y rechazos esperados:

```bash
pip install 'jsonschema[format]'
python -m unittest discover -s tests -v
```
