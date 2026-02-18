# VB Converter - Kubernetes Deployment

Deze directory bevat alle Kubernetes manifests voor het deployen van de VB Converter applicatie.

## Structuur

```
k8s/
├── base/                      # Base configuratie
│   ├── namespace.yaml         # Namespace definitie
│   ├── configmap.yaml         # Niet-gevoelige configuratie
│   ├── secrets.yaml           # Secret template (NIET voor productie!)
│   ├── backend-deployment.yaml    # FastAPI backend
│   ├── frontend-deployment.yaml   # React/Nginx frontend
│   ├── postgres-statefulset.yaml  # PostgreSQL database
│   ├── ingress.yaml           # Nginx Ingress routing
│   └── kustomization.yaml     # Kustomize configuratie
├── overlays/
│   ├── dev/                   # Development overrides
│   ├── staging/               # Staging overrides
│   └── prod/                  # Production overrides
└── README.md                  # Dit bestand
```

## Vereisten

- Kubernetes cluster (v1.25+)
- kubectl CLI
- Nginx Ingress Controller
- (Optioneel) cert-manager voor TLS
- (Optioneel) metrics-server voor HPA

## Quick Start - Development

### 1. Nginx Ingress Controller installeren

```bash
# Voor cloud providers (AWS, GCP, Azure)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.9.4/deploy/static/provider/cloud/deploy.yaml

# Voor minikube
minikube addons enable ingress

# Voor kind
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.9.4/deploy/static/provider/kind/deploy.yaml
```

### 2. Docker images bouwen

```bash
# Backend
docker build -t hienfeld-api:latest -f Dockerfile.backend .

# Frontend
docker build -t hienfeld-frontend:latest -f Dockerfile.frontend .

# Voor minikube: gebruik minikube docker-env
eval $(minikube docker-env)
docker build -t hienfeld-api:latest -f Dockerfile.backend .
docker build -t hienfeld-frontend:latest -f Dockerfile.frontend .
```

### 3. Secrets aanmaken

**BELANGRIJK:** Gebruik nooit de template secrets in productie!

```bash
# Genereer een veilige secret key
SECRET_KEY=$(openssl rand -hex 32)

# Maak secrets aan
kubectl create namespace vb-converter

kubectl create secret generic hienfeld-secrets \
  --namespace vb-converter \
  --from-literal=POSTGRES_URL='postgresql://hienfeld:SecurePassword123@hienfeld-postgres:5432/hienfeld' \
  --from-literal=SECRET_KEY="${SECRET_KEY}" \
  --from-literal=OPENAI_API_KEY=''

kubectl create secret generic hienfeld-postgres-secrets \
  --namespace vb-converter \
  --from-literal=POSTGRES_USER='hienfeld' \
  --from-literal=POSTGRES_PASSWORD='SecurePassword123' \
  --from-literal=POSTGRES_DB='hienfeld'
```

### 4. Applicatie deployen

```bash
# Preview wat er gedeployed wordt
kubectl kustomize k8s/base/

# Deploy naar cluster
kubectl apply -k k8s/base/

# Volg de deployment
kubectl -n vb-converter get pods -w
```

### 5. Toegang tot de applicatie

```bash
# Check Ingress IP/hostname
kubectl -n vb-converter get ingress

# Voor minikube: tunnel starten
minikube tunnel

# Of port-forward voor lokale toegang
kubectl -n vb-converter port-forward svc/hienfeld-frontend 8080:80
kubectl -n vb-converter port-forward svc/hienfeld-api 8000:8000
```

Open http://localhost:8080 in je browser.

## Production Deployment

### 1. Overlay gebruiken

```bash
# Bekijk production configuratie
kubectl kustomize k8s/overlays/prod/

# Deploy naar production
kubectl apply -k k8s/overlays/prod/
```

### 2. Aanbevelingen voor productie

- **Secrets:** Gebruik Sealed Secrets, External Secrets, of Vault
- **Database:** Gebruik managed PostgreSQL (RDS, Cloud SQL, Azure Database)
- **TLS:** Configureer cert-manager met Let's Encrypt
- **Monitoring:** Deploy Prometheus + Grafana stack
- **Logging:** Configureer Loki of ELK stack
- **Backup:** Stel Velero in voor cluster backup

### 3. TLS configureren

```bash
# Installeer cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.0/cert-manager.yaml

# Maak ClusterIssuer aan
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

Uncomment de TLS sectie in `ingress.yaml` en pas de hostname aan.

## Monitoring & Debugging

### Logs bekijken

```bash
# Alle pods
kubectl -n vb-converter logs -l app.kubernetes.io/part-of=vb-converter

# Backend logs
kubectl -n vb-converter logs -l app.kubernetes.io/name=hienfeld-api -f

# Frontend logs
kubectl -n vb-converter logs -l app.kubernetes.io/name=hienfeld-frontend -f

# PostgreSQL logs
kubectl -n vb-converter logs -l app.kubernetes.io/name=hienfeld-postgres -f
```

### Resource status

```bash
# Overzicht van alle resources
kubectl -n vb-converter get all

# Deployment status
kubectl -n vb-converter describe deployment hienfeld-api

# Pod details
kubectl -n vb-converter describe pod <pod-name>

# Events
kubectl -n vb-converter get events --sort-by=.lastTimestamp
```

### Troubleshooting

```bash
# Check pod status
kubectl -n vb-converter get pods

# Shell in pod
kubectl -n vb-converter exec -it <pod-name> -- /bin/sh

# Database connectie testen
kubectl -n vb-converter exec -it <backend-pod> -- python -c "from hienfeld_api.database import engine; print(engine.url)"

# Netwerk debugging
kubectl -n vb-converter run debug --rm -it --image=busybox -- /bin/sh
```

## Scaling

### Handmatig schalen

```bash
# Backend schalen
kubectl -n vb-converter scale deployment hienfeld-api --replicas=3

# Frontend schalen
kubectl -n vb-converter scale deployment hienfeld-frontend --replicas=3
```

### Horizontal Pod Autoscaler (HPA)

```bash
# HPA voor backend
kubectl -n vb-converter autoscale deployment hienfeld-api \
  --min=2 --max=10 --cpu-percent=70

# Bekijk HPA status
kubectl -n vb-converter get hpa
```

## Cleanup

```bash
# Verwijder alle resources
kubectl delete -k k8s/base/

# Of alleen de namespace (verwijdert alles erin)
kubectl delete namespace vb-converter

# PersistentVolumeClaims blijven standaard behouden
# Handmatig verwijderen indien gewenst:
kubectl delete pvc -n vb-converter --all
```

## Architectuur Diagram

```
                    ┌─────────────────────────────────────────┐
                    │            Nginx Ingress                │
                    │   (TLS termination, rate limiting)      │
                    └──────────────┬──────────────────────────┘
                                   │
              ┌────────────────────┴─────────────────────┐
              │                                          │
              ▼                                          ▼
    ┌─────────────────┐                        ┌─────────────────┐
    │  /api/*         │                        │  /*             │
    │  Backend Svc    │                        │  Frontend Svc   │
    │  (ClusterIP)    │                        │  (ClusterIP)    │
    └────────┬────────┘                        └────────┬────────┘
             │                                          │
    ┌────────┴────────┐                        ┌────────┴────────┐
    │                 │                        │                 │
    ▼                 ▼                        ▼                 ▼
┌───────┐       ┌───────┐                ┌───────┐       ┌───────┐
│ API   │       │ API   │                │Nginx  │       │Nginx  │
│ Pod 1 │       │ Pod 2 │                │ Pod 1 │       │ Pod 2 │
└───┬───┘       └───┬───┘                └───────┘       └───────┘
    │               │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │  PostgreSQL   │
    │  StatefulSet  │
    │  (5Gi PVC)    │
    └───────────────┘
```

## Versioning

| Component | Versie |
|-----------|--------|
| Kubernetes | 1.25+ |
| Nginx Ingress | 1.9.x |
| PostgreSQL | 16.x |
| cert-manager | 1.14.x |
