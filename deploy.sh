#!/bin/bash
set -e

IMAGE="asia-northeast3-docker.pkg.dev/mt-further-practice/tft-api/tft-api-server:latest"

echo "▶ 빌드 시작..."
docker build --platform linux/amd64 -t $IMAGE .

echo "▶ Artifact Registry 푸시..."
docker push $IMAGE

echo "▶ Cloud Run 배포..."
gcloud run deploy tft-api-server \
  --project mt-further-practice \
  --image $IMAGE \
  --region asia-northeast3 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 3600

echo "✅ 배포 완료"
