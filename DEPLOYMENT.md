# Deployment Guide

This guide outlines the steps to deploy the Lyo backend to different environments.

## Prerequisites

- Docker and docker-compose
- Kubernetes cluster access (for production)
- PostgreSQL database
- Redis instance
- Google Cloud account (for Firestore, Pub/Sub, Storage)

## Deployment Options

### 1. Docker Compose (Development/Staging)

**Setup:**

1. Create environment file
   ```bash
   cp .env.example .env
   # Edit .env with appropriate settings
   ```

2. Build and start services
   ```bash
   docker-compose up --build
   ```

3. Create an admin user
   ```bash
   docker-compose exec app python -m scripts.create_admin --email admin@example.com --password secure-password
   ```

### 2. Kubernetes (Production)

**Prerequisites:**

- kubectl configured to access your Kubernetes cluster
- Helm installed

**Setup:**

1. Configure Kubernetes secrets
   ```bash
   kubectl create namespace lyo
   
   # Create secret for database credentials
   kubectl create secret generic lyo-db-credentials \
       --namespace=lyo \
       --from-literal=POSTGRES_USER=postgres \
       --from-literal=POSTGRES_PASSWORD=secure-password \
       --from-literal=POSTGRES_DB=lyo
   
   # Create secret for JWT and other secrets
   kubectl create secret generic lyo-app-secrets \
       --namespace=lyo \
       --from-literal=SECRET_KEY=your-secret-key-here
   
   # Create config map for environment variables
   kubectl create configmap lyo-app-config \
       --namespace=lyo \
       --from-literal=ENVIRONMENT=production \
       --from-literal=LOG_LEVEL=INFO
   ```

2. Deploy using Helm
   ```bash
   helm upgrade --install lyo ./infra/helm \
       --namespace=lyo \
       --set image.tag=latest \
       --wait
   ```

3. Create an admin user
   ```bash
   kubectl exec -it deploy/lyo-backend -n lyo -- python -m scripts.create_admin --email admin@example.com --password secure-password
   ```

### 3. Cloud Platforms

#### Google Cloud Run

1. Build and push Docker image
   ```bash
   export PROJECT_ID=your-project-id
   export IMAGE=gcr.io/$PROJECT_ID/lyo-backend:latest
   
   docker build -t $IMAGE .
   docker push $IMAGE
   ```

2. Deploy to Cloud Run
   ```bash
   gcloud run deploy lyo-backend \
       --image=$IMAGE \
       --platform=managed \
       --region=us-central1 \
       --allow-unauthenticated \
       --set-env-vars="ENVIRONMENT=production,LOG_LEVEL=INFO" \
       --set-secrets="SECRET_KEY=lyo-secret-key:latest,POSTGRES_PASSWORD=lyo-db-password:latest" \
       --cpu=2 \
       --memory=2Gi \
       --concurrency=80
   ```

#### AWS Elastic Beanstalk

1. Create Elastic Beanstalk environment
   ```bash
   eb init -p docker lyo-backend
   eb create production
   ```

2. Set environment variables
   ```bash
   eb setenv \
       ENVIRONMENT=production \
       LOG_LEVEL=INFO \
       SECRET_KEY=your-secret-key-here
   ```

3. Deploy the application
   ```bash
   eb deploy
   ```

## Post-Deployment Tasks

1. Run database migrations
   ```bash
   # For Docker Compose
   docker-compose exec app alembic upgrade head
   
   # For Kubernetes
   kubectl exec -it deploy/lyo-backend -n lyo -- alembic upgrade head
   ```

2. Verify deployment
   ```bash
   curl https://your-deployment-url/api/v1/health/deep
   ```

3. Set up monitoring and alerts
   - Configure Prometheus and Grafana dashboards
   - Set up alerts for error rates, latency, and resource utilization

## Security Considerations

- Ensure PostgreSQL and Redis instances are properly secured
- Set up a proper network security policy to restrict access
- Use HTTPS for all endpoints in production
- Rotate secrets regularly
- Set up log monitoring for security events

## Scaling

- Horizontally scale the API by increasing the number of replicas
- Enable Redis caching for frequently accessed data
- Set appropriate resource limits for containers
- Configure auto-scaling based on CPU and memory usage
