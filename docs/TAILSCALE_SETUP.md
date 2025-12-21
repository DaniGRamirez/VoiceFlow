# Configuración VoiceFlow con Tailscale

Guía para exponer VoiceFlow a través de Tailscale y enviar intents desde iPhone.

## Requisitos Previos

1. Tailscale instalado en Windows y iPhone
2. Ambos dispositivos conectados a la misma Tailnet
3. VoiceFlow corriendo con configuración Tailscale habilitada

## Configuración

### 1. Editar `config.json`

Añade la sección `tailscale`:

```json
{
    "tailscale": {
        "enabled": true,
        "bind_address": "0.0.0.0",
        "bearer_token": "tu-token-secreto-aqui",
        "allowed_ips": [],
        "log_requests": true
    }
}
```

| Campo | Descripción |
|-------|-------------|
| `enabled` | `true` para activar acceso remoto |
| `bind_address` | `0.0.0.0` (todas las interfaces) o IP Tailscale específica |
| `bearer_token` | Token secreto para autenticación (REQUERIDO) |
| `allowed_ips` | Lista blanca de IPs (vacío = solo validar token) |
| `log_requests` | Guardar métricas de latencia en `logs/tailscale_metrics.json` |

### 2. Generar un token seguro

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Obtener tu IP Tailscale

```bash
# Windows PowerShell
tailscale ip -4

# O ver en Tailscale admin console
```

Tu IP será algo como `100.x.x.x`.

## Configuración Windows Firewall

### Opción A: PowerShell (Administrador)

```powershell
# Permitir puerto 8765 entrante desde red Tailscale (100.x.x.x)
New-NetFirewallRule -DisplayName "VoiceFlow Tailscale" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 8765 `
    -RemoteAddress 100.0.0.0/8 `
    -Action Allow

# Verificar regla creada
Get-NetFirewallRule -DisplayName "VoiceFlow Tailscale"
```

### Opción B: GUI Windows Firewall

1. Abrir "Windows Defender Firewall con seguridad avanzada"
2. Click derecho en "Reglas de entrada" → "Nueva regla"
3. Seleccionar "Puerto" → Siguiente
4. TCP, puerto específico: `8765` → Siguiente
5. "Permitir la conexión" → Siguiente
6. Marcar: Dominio, Privado, Público → Siguiente
7. Nombre: "VoiceFlow Tailscale" → Finalizar
8. Doble click en la regla → Pestaña "Ámbito"
9. En "Dirección IP remota", agregar: `100.0.0.0/8`

## Endpoints Disponibles

| Endpoint | Método | Auth | Descripción |
|----------|--------|------|-------------|
| `/health` | GET | No | Verificar conectividad |
| `/ping` | GET | Sí | Medir latencia |
| `/api/intent` | POST | Sí | Enviar intent (accept/reject) |
| `/api/metrics` | GET | Sí | Ver estadísticas de latencia |
| `/api/status` | GET | No | Estado del servidor |
| `/api/notifications` | GET | No | Listar notificaciones activas |

## Probar Conectividad

### Desde iPhone (Terminal o app HTTP)

```bash
# Health check (sin auth)
curl http://100.x.x.x:8765/health

# Ping (con auth)
curl -H "Authorization: Bearer TU_TOKEN" \
     http://100.x.x.x:8765/ping

# Enviar intent
curl -X POST \
     -H "Authorization: Bearer TU_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"correlation_id":"abc123","intent":"accept"}' \
     http://100.x.x.x:8765/api/intent
```

### Usando MagicDNS

Si tienes MagicDNS habilitado en tu tailnet:

```bash
curl http://tu-pc.tailnet-name.ts.net:8765/health
```

## Configurar iOS Shortcuts

### Shortcut: Accept Intent

1. Crear nuevo Shortcut
2. Añadir acción "Get Contents of URL"
3. Configurar:
   - URL: `http://100.x.x.x:8765/api/intent`
   - Method: POST
   - Headers:
     - `Authorization`: `Bearer TU_TOKEN`
     - `Content-Type`: `application/json`
   - Request Body: JSON
     ```json
     {
       "correlation_id": "Shortcut Input",
       "intent": "accept"
     }
     ```

### Shortcut: Reject Intent

Igual que Accept pero con `"intent": "reject"`.

### Shortcut: Health Check

1. Crear nuevo Shortcut
2. Añadir acción "Get Contents of URL"
3. URL: `http://100.x.x.x:8765/health`
4. Añadir "Show Result" para ver la respuesta

## Métricas y Monitoring

### Ver estadísticas de latencia

```bash
curl -H "Authorization: Bearer TU_TOKEN" \
     http://100.x.x.x:8765/api/metrics
```

Respuesta ejemplo:

```json
{
  "stats": {
    "count": 150,
    "median_ms": 45.2,
    "p95_ms": 180.5,
    "min_ms": 12.1,
    "max_ms": 450.3
  },
  "recent": [...]
}
```

### Targets de Rendimiento

| Métrica | Target | Aceptable |
|---------|--------|-----------|
| Latencia mediana | < 200ms | < 300ms |
| P95 | < 500ms | < 800ms |
| Reliability | > 99% | > 95% |

## Troubleshooting

### Error 401 Unauthorized

- Verificar que el Bearer token coincide con `config.json`
- Formato correcto: `Authorization: Bearer TU_TOKEN`

### Error 403 Forbidden

- IP no está en la lista `allowed_ips`
- Verificar que ambos dispositivos están en la misma Tailnet

### Timeout / No respuesta

1. Verificar que VoiceFlow está corriendo
2. Probar desde localhost primero: `curl http://localhost:8765/health`
3. Verificar regla de firewall
4. Verificar que Tailscale está conectado en ambos dispositivos

### PC entra en suspensión

- Configurar Windows para no suspender mientras VoiceFlow está activo
- O usar "Wake on LAN" via Tailscale

### Latencia alta en cellular

- Es normal hasta ~500ms en 4G/5G
- La app debe mostrar estado "pending" visible
- Implementar retry automático si falla

## Seguridad

- **Token**: Guardado en texto plano en `config.json`. Proteger permisos del archivo.
- **Tailscale**: Proporciona encriptación punto a punto. No necesita HTTPS adicional.
- **Localhost**: Siempre permitido sin autenticación para mantener compatibilidad.
- **Logs**: Las métricas incluyen IP remota pero no el contenido de los requests.
