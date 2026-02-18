# VB Converter Monitoring Setup

Dit document beschrijft hoe je de Prometheus + Grafana monitoring stack opzet voor de VB Converter applicatie.

## Quick Start

### 1. Start de monitoring stack

```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

### 2. Controleer dat alles draait

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (login: admin/admin)

### 3. Start de VB Converter API

```bash
uvicorn hienfeld_api.app:app --reload --port 8000
```

### 4. Bekijk de metrics

Open Grafana en navigeer naar het "VB Converter - API Dashboard".

## Beschikbare Metrics

### Counters (totalen)

| Metric | Labels | Beschrijving |
|--------|--------|--------------|
| `vb_analysis_requests_total` | status | Totaal aantal analyse requests (started/completed/failed/cancelled) |
| `vb_analysis_errors_total` | error_type | Totaal aantal errors (validation/processing/timeout/unknown) |
| `vb_http_requests_total` | method, endpoint, status_code | HTTP requests per endpoint |
| `vb_rows_processed_total` | analysis_mode | Verwerkte rijen per mode |

### Gauges (huidige waarden)

| Metric | Labels | Beschrijving |
|--------|--------|--------------|
| `vb_active_jobs` | - | Aantal actieve analyse jobs |
| `vb_cache_entries` | cache_type | Cache entries (nlp/embeddings/tfidf) |

### Histograms (distributies)

| Metric | Labels | Buckets | Beschrijving |
|--------|--------|---------|--------------|
| `vb_analysis_duration_seconds` | analysis_mode | 10s, 30s, 1m, 2m, 5m, 10m, 15m, 30m | Analyse doorlooptijd |
| `vb_http_request_duration_seconds` | method, endpoint | 10ms - 10s | HTTP request latency |
| `vb_clustering_duration_seconds` | - | 1s - 5m | Clustering fase duur |
| `vb_ingestion_duration_seconds` | - | 0.5s - 30s | File ingestion duur |
| `vb_export_duration_seconds` | - | 0.5s - 30s | Excel export duur |

## Prometheus Queries

### Nuttige PromQL queries

**Analyse success rate (laatste uur):**
```promql
sum(rate(vb_analysis_requests_total{status="completed"}[1h]))
/
sum(rate(vb_analysis_requests_total{status=~"completed|failed"}[1h]))
```

**Gemiddelde analyse tijd per mode:**
```promql
histogram_quantile(0.50, sum(rate(vb_analysis_duration_seconds_bucket[1h])) by (le, analysis_mode))
```

**Error rate per type:**
```promql
sum(rate(vb_analysis_errors_total[1h])) by (error_type)
```

**Requests per seconde:**
```promql
sum(rate(vb_http_requests_total[5m])) by (endpoint)
```

## Productie Setup

### Environment Variables

Voor productie, pas het target aan in `monitoring/prometheus.yml`:

```yaml
- job_name: 'vb-converter-api-production'
  static_configs:
    - targets: ['api.vbconverter.example.com:443']
      labels:
        environment: 'production'
  scheme: https
```

### Security

De `/metrics` endpoint is publiek toegankelijk. In productie:

1. **Network isolation**: Beperk toegang tot de metrics endpoint via firewall/network policies
2. **Basic auth**: Voeg authenticatie toe aan Prometheus scraper
3. **HTTPS**: Gebruik TLS voor metrics verkeer

### Alerting

Voeg alerting rules toe in `monitoring/rules/`:

```yaml
# monitoring/rules/vb-converter.yml
groups:
  - name: vb-converter
    rules:
      - alert: HighErrorRate
        expr: sum(rate(vb_analysis_errors_total[5m])) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"

      - alert: SlowAnalysis
        expr: histogram_quantile(0.95, sum(rate(vb_analysis_duration_seconds_bucket[5m])) by (le)) > 600
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Analysis taking longer than 10 minutes"
```

## Data Retention

Standaard bewaart Prometheus 30 dagen aan data. Pas aan in `docker-compose.monitoring.yml`:

```yaml
command:
  - '--storage.tsdb.retention.time=90d'  # 90 dagen
```

## Troubleshooting

### Prometheus kan API niet bereiken

1. Check of de API draait: `curl http://localhost:8000/metrics`
2. Check Docker network: `docker network inspect vb_monitoring`
3. Voor Windows/Mac: `host.docker.internal` moet resolven naar host

### Grafana toont geen data

1. Check Prometheus datasource in Grafana (Configuration > Data Sources)
2. Controleer of Prometheus data heeft: http://localhost:9090/targets
3. Wacht 15-30 seconden voor eerste scrape

### Metrics niet zichtbaar

1. Check de app logs voor errors bij startup
2. Verify dat prometheus-client is geinstalleerd: `pip show prometheus-client`
3. Test de endpoint direct: `curl http://localhost:8000/metrics`
