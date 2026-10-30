# Contratos oficiales EnergyShark v3.0.2

Los 46 schemas de este directorio y los 261 fixtures de `docs/examples/v3/` son copias sin cambios del tag oficial [`v3.0.2`](https://github.com/iic2173/energyshark-contracts/tree/v3.0.2), commit `62f6cf40768b6e42717d126e528dcd944e5bc0e3`. `SOURCE_SHA256.json` fija el hash de cada schema. `docs/openapi/wallet-v3-official.yaml` copia el OpenAPI de Wallet del mismo tag.

Los schemas incluyen 22 mensajes AMQP, fragmentos comunes, razones, token de swap, cuerpos REST Wallet y el índice del protocolo. `tests/test_v3_contracts.py` valida schemas, fixtures válidos/inválidos y los ACK/NACK producidos por las funciones reales del Connector. CI descarga el backend público sólo para esta prueba de emisor; ninguna prueba contacta el broker ni Wallet.

`docs/openapi/openapi.yaml` documenta la API propia generada desde la aplicación FastAPI del backend E2. La versión E1 queda en `openapi-v2.yaml`.
