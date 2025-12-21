#!/usr/bin/env python3
"""
Script de prueba para conectividad Tailscale.

Uso:
    python scripts/test_tailscale.py --host 100.x.x.x --token TU_TOKEN
    python scripts/test_tailscale.py --host localhost --token test  # Prueba local
"""

import argparse
import time
import json
import statistics
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def test_health(base_url: str) -> bool:
    """Prueba endpoint /health (sin auth)."""
    try:
        req = Request(f"{base_url}/health", method="GET")
        req.add_header("Accept", "application/json")
        response = urlopen(req, timeout=5)
        data = json.loads(response.read())
        print(f"  Status: {data.get('status')}")
        print(f"  Service: {data.get('service')}")
        print(f"  Tailscale enabled: {data.get('tailscale_enabled')}")
        print(f"  Uptime: {data.get('uptime_seconds', 0):.1f}s")
        return True
    except HTTPError as e:
        print(f"  HTTP Error: {e.code} - {e.reason}")
        return False
    except URLError as e:
        print(f"  Connection Error: {e.reason}")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False


def test_ping(base_url: str, token: str, count: int = 10) -> list:
    """Prueba endpoint /ping y mide latencia."""
    latencies = []

    for i in range(count):
        start = time.time()
        try:
            req = Request(f"{base_url}/ping", method="GET")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Accept", "application/json")
            response = urlopen(req, timeout=5)
            latency_ms = (time.time() - start) * 1000
            data = json.loads(response.read())
            latencies.append(latency_ms)
            print(f"  [{i+1:2d}] {latency_ms:6.1f}ms - server_time: {data.get('server_time', 'N/A')[:19]}")
        except HTTPError as e:
            print(f"  [{i+1:2d}] HTTP {e.code}: {e.reason}")
        except URLError as e:
            print(f"  [{i+1:2d}] Connection Error: {e.reason}")
        except Exception as e:
            print(f"  [{i+1:2d}] Error: {e}")

        time.sleep(0.1)

    return latencies


def test_intent(base_url: str, token: str, correlation_id: str = "test-id") -> bool:
    """Prueba endpoint /api/intent."""
    try:
        payload = {
            "correlation_id": correlation_id,
            "intent": "accept",
            "source": "test_script"
        }
        data = json.dumps(payload).encode("utf-8")

        req = Request(f"{base_url}/api/intent", data=data, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")

        response = urlopen(req, timeout=5)
        result = json.loads(response.read())
        print(f"  Success: {result.get('success')}")
        print(f"  Intent: {result.get('intent')}")
        print(f"  Status: {result.get('status')}")
        print(f"  Processing: {result.get('processing_ms', 0):.1f}ms")
        return True
    except HTTPError as e:
        if e.code == 404:
            print(f"  404 - No hay notificación activa (esperado en test)")
            return True  # Es válido que no haya notificación
        elif e.code == 401:
            print(f"  401 - Token inválido o faltante")
            return False
        elif e.code == 403:
            print(f"  403 - IP no permitida")
            return False
        else:
            print(f"  HTTP {e.code}: {e.reason}")
            return False
    except URLError as e:
        print(f"  Connection Error: {e.reason}")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False


def test_metrics(base_url: str, token: str) -> bool:
    """Prueba endpoint /api/metrics."""
    try:
        req = Request(f"{base_url}/api/metrics", method="GET")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/json")

        response = urlopen(req, timeout=5)
        result = json.loads(response.read())
        stats = result.get("stats", {})

        print(f"  Total requests: {stats.get('count', 0)}")
        if stats.get("count", 0) > 0:
            print(f"  Median: {stats.get('median_ms', 0):.1f}ms")
            print(f"  P95: {stats.get('p95_ms', 0):.1f}ms")
            print(f"  Min: {stats.get('min_ms', 0):.1f}ms")
            print(f"  Max: {stats.get('max_ms', 0):.1f}ms")
        return True
    except HTTPError as e:
        if e.code == 401:
            print(f"  401 - Token inválido o faltante")
        else:
            print(f"  HTTP {e.code}: {e.reason}")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Test Tailscale connectivity to VoiceFlow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python scripts/test_tailscale.py --host localhost --token test
  python scripts/test_tailscale.py --host 100.64.0.1 --token mi-token-secreto
  python scripts/test_tailscale.py --host mi-pc.tailnet.ts.net --token abc123 --pings 50
        """
    )
    parser.add_argument("--host", required=True, help="IP o hostname (100.x.x.x o MagicDNS)")
    parser.add_argument("--port", type=int, default=8765, help="Puerto (default: 8765)")
    parser.add_argument("--token", required=True, help="Bearer token")
    parser.add_argument("--pings", type=int, default=10, help="Número de pings (default: 10)")
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"

    print()
    print("=" * 50)
    print("  VoiceFlow Tailscale Connectivity Test")
    print("=" * 50)
    print(f"  URL: {base_url}")
    print(f"  Token: {args.token[:8]}...")
    print()

    # Test 1: Health
    print("[1/4] Health check (sin auth)...")
    if not test_health(base_url):
        print("\n[ABORT] No se puede conectar al servidor")
        print("Verifica que VoiceFlow está corriendo y el firewall permite conexiones.")
        return 1

    # Test 2: Ping con auth
    print(f"\n[2/4] Ping x{args.pings} (con auth)...")
    latencies = test_ping(base_url, args.token, args.pings)

    if latencies:
        latencies_sorted = sorted(latencies)
        n = len(latencies_sorted)

        print(f"\n  Estadísticas ({n} samples):")
        print(f"    Min:    {min(latencies):.1f}ms")
        print(f"    Median: {statistics.median(latencies):.1f}ms")
        p95_idx = int(n * 0.95)
        p95 = latencies_sorted[p95_idx] if p95_idx < n else latencies_sorted[-1]
        print(f"    P95:    {p95:.1f}ms")
        print(f"    Max:    {max(latencies):.1f}ms")
        print(f"    Avg:    {statistics.mean(latencies):.1f}ms")

        # Verificar targets
        median = statistics.median(latencies)
        if median < 200 and p95 < 500:
            print(f"\n  [PASS] Cumple targets UX (median<200ms, P95<500ms)")
        elif median < 300 and p95 < 800:
            print(f"\n  [WARN] Aceptable pero no óptimo")
        else:
            print(f"\n  [FAIL] No cumple targets - latencia muy alta")
    else:
        print("\n  [FAIL] No se obtuvieron latencias válidas")

    # Test 3: Intent
    print(f"\n[3/4] Intent test (con auth)...")
    test_intent(base_url, args.token)

    # Test 4: Metrics
    print(f"\n[4/4] Metrics (con auth)...")
    test_metrics(base_url, args.token)

    print()
    print("=" * 50)
    print("  Pruebas completadas")
    print("=" * 50)
    print()

    return 0


if __name__ == "__main__":
    exit(main())
