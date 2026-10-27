# Contratos v3 de EnergyShark (E2-024)

## Autoridad del contrato y origen

Los **46 schemas JSON** en `schemas/` y `wallet.openapi.yaml` son **copias sin modificaciones** del repositorio oficial del curso [`iic2173/energyshark-contracts`](https://github.com/iic2173/energyshark-contracts), **tag `v3.0.1`**, commit `6cae6dcf1be954eb80c28fa34af52b1fcadf91de`. Los hashes SHA-256 se almacenan en `SOURCE_SHA256.json`. Los `$id` y `$ref` se mantienen como en origen.

En caso de diferencia con el texto explicativo, mandan los schemas del curso. La documentación interna y los ejemplos no redefinen el contrato. `wallet.openapi.yaml` es la **API externa de la wallet**, no el OpenAPI de nuestro backend: el OpenAPI propio de la organización está en `docs/openapi/openapi.yaml` y deberá actualizarse en E2-077.

## Estructura

- `schemas/amqp/`: **22** mensajes AMQP, tanto de mercado y ciudades pares como de central y wallet.
- `schemas/common/`: envelope, sender, cycle, importes `CR` y `KWH`, balances, etc.
- `schemas/wallet/`: cuerpos de la wallet REST, incluidas respuestas HTTP, balance, swaps, JWKS y leaderboard.
- `schemas/reason/`: motivos y códigos de rechazo, por portador.
- `schemas/token/`: claims del JWT `swapToken` (no verifica la firma criptográfica).
- `schemas/index.schema.json`: unión de tipos para validación/generación de modelos.
- `wallet.openapi.yaml`: OpenAPI 3.1 **oficial de wallet**.
- `../examples/v3/`: ejemplos sintéticos propios, con manifiesto y casos válidos/ inválidos.

No se tocaron los archivos `docs/schemas/v2/` ni `docs/examples/v2/`: se mantienen como documentación histórica de E1, incluidos los tipos retirados. **No se debe usar `v2` como contrato de validación del protocolo v3.**

## Validación estructural y límites

Los ejemplos locales se validan con `python3 scripts/check_v3_examples.py` (requiere `jsonschema[format]`). Se validan con el **validador 2020-12**, `FormatChecker` y un registro local de referencias basado en `$id`. No se descargan URLs de los schemas. Este chequeo es la validación inicial de E2-024; E2-025 extenderá la suite para validar los mensajes realmente emitidos por el nodo y ejecutarla en CI contra el curso.

- Los mensajes de ciudad son *abiertos*: campos extra que el schema oficial permite **no** deben declararse inválidos solo por no figurar en el ejemplo, como `bid.data.price` adicional. No significa que ese precio tenga efecto: el vendedor sigue fijando el precio de la oferta.
- Cantidades enteras `KWH` pueden ser numéricamente cero o negativas **a nivel de schema** según el campo: reglas como `minBid`, disponibilidad de wallet o restricciones de negocio requieren validación de runtime. Por ello un `bid` de cantidad 0 **no** debe ser fixture JSON inválido.
- El `error` v3 pertenece al catálogo oficial de razones. Errores retirados de la E1 no se emiten como v3.
- Los mensajes emitidos por central o wallet pueden ser cerrados (`unevaluatedProperties: false`): no insertar `cityId` ni datos auxiliares que el contrato no permite.
- JSON Schema no compara `msgId != idpk`, no verifica `user_id` AMQP, ventanas del mercado, que HTTP 202 sea liquidación ni la firma JWT ES256/JWKS.

## Coherencia arquitectónica

**AD4:** serializar bids por oferta, impedir reservas duplicadas y no hacer llamadas wallet bajo el bloqueo es lógica del backend, no del schema.

**AD5:** wallet es la autoridad, eventos `swap-settled` y `trade-recorded` se deduplican y reconcilian. `202 Accepted` no significa `settled`, y el token firmado requiere validación de firma y claims en runtime.

**AD6:** configuración de estrategias versionada por ciclo y con aplicación en el siguiente ciclo es persistencia de backend, no un campo extra del protocolo AMQP.

## Nota de cambios respecto del primer paquete provisional

Comparación contra fuente oficial: 2 fixtures considerados válidos eran rechazados (`distance-table` con `cityId` y `error` con razón E1 no permitida). Otros 4 considerados inválidos eran estructuralmente válidos (cantidad cero en `bid`, cantidad negativa en `offer-updated`, `bid` con precio adicional y `offer` con campo extra). Todos fueron corregidos o sustituidos. Los schemas ahora son idénticos a los del curso, no reinterpretaciones.
