# Docker Compose 관리 및 자동 복구 시스템 가이드

이 문서는 MedSAM2 프로젝트의 Docker Compose 구성, 관리 방법, 그리고 새롭게 도입된 **자동 복구(Auto-Recovery) 시스템**의 작동 원리에 대해 설명합니다.

## 1. Docker Compose 구조 (`docker-compose.yml`)

프로젝트는 마이크로서비스 아키텍처를 따르며, `docker-compose.yml` 파일에 모든 서비스가 정의되어 있습니다.

### 주요 서비스

| 서비스명 | 역할 | 포트 | 비고 |
| :--- | :--- | :--- | :--- |
| `redis` | 메시지 브로커 및 결과 저장소 | 6380:6379 | `healthcheck` 포함 |
| `api` | FastAPI 백엔드 서버 | 8000:8000 | `autoheal=true` 라벨 |
| `worker1` ~ `worker8` | AI 모델 추론을 담당하는 Celery 워커 | - | 각 워커별 고유 `hostname` 및 MIG GPU 할당 |
| `monitor` | Celery 모니터링 (Flower) | 5556:5555 | `autoheal=true` 라벨 |
| `autoheal` | 비정상 컨테이너 자동 재시작 관리자 | - | Docker 소켓 마운트 필요 |

---

## 2. 자동 복구 시스템 (Auto-Recovery)

서버가 멈추거나(Hang), 워커가 응답하지 않는 상황을 방지하기 위해 **Healthcheck**와 **Autoheal**을 결합한 자동 복구 시스템을 구축했습니다.

### 작동 원리

1.  **Healthcheck (건강 검진)**:
    -   각 컨테이너는 주기적으로 자신의 상태를 체크합니다.
    -   **API**: `curl -f http://localhost:8000/health`
    -   **Worker**: `celery inspect ping` (Celery 메인 루프 응답 확인)
    -   **Monitor**: `curl -f http://localhost:5555/`

2.  **Unhealthy 상태 감지**:
    -   만약 컨테이너가 `interval`(예: 60초) 동안 `retries`(예: 3회) 이상 응답하지 않으면, Docker는 해당 컨테이너의 상태를 `unhealthy`로 변경합니다.

3.  **Autoheal (자동 치유)**:
    -   `autoheal` 컨테이너는 Docker 이벤트를 실시간으로 감시합니다.
    -   어떤 컨테이너가 `unhealthy` 상태로 변하면, 즉시 해당 컨테이너를 **재시작(Restart)** 시킵니다.

### 설정 상세 (튜닝됨)

안정적인 운영을 위해 Healthcheck 파라미터가 튜닝되었습니다:

-   **interval**: `60s` (너무 자주 체크하여 부하를 주는 것을 방지)
-   **timeout**: `30s` (워커가 무거운 작업을 할 때 타임아웃 되는 것을 방지)
-   **start_period**: `60s` (초기 모델 로딩 시간을 충분히 보장)
-   **retries**: `3` (일시적인 네트워크 오류 무시)

---

## 3. 관리 명령어

### 서비스 상태 확인
```bash
# 컨테이너 상태 및 Health 상태 확인 (healthy/unhealthy)
docker compose ps
```

### 로그 확인
```bash
# 전체 로그 (실시간)
docker compose logs -f

# 특정 워커 로그
docker compose logs -f worker1

# Autoheal 로그 (재시작 기록 확인)
docker compose logs -f autoheal
```

### 수동 재시작 (필요시)
```bash
# 특정 서비스만 재시작
docker compose restart worker1

# 전체 재시작
docker compose down
docker compose up -d
```

### GPU 모니터링
```bash
# 워커 내부에서 nvidia-smi 실행
docker compose exec worker1 nvidia-smi
```

---

## 4. 트러블슈팅

**Q: 워커가 계속 재시작됩니다.**
A: `docker compose logs workerX`를 확인하세요.
-   **메모리 부족(OOM)**: GPU 메모리가 부족하여 프로세스가 죽었을 수 있습니다.
-   **Healthcheck 실패**: 워커가 너무 바빠서 30초 내에 응답을 못했을 수 있습니다. 이 경우 `docker-compose.yml`에서 `timeout`을 늘려야 합니다.

**Q: Monitor 서비스가 Unhealthy입니다.**
A: Monitor(Flower)는 5555 포트를 사용합니다. Healthcheck가 5555 포트를 보고 있는지 확인하세요. (기존 8000 포트 체크 시 실패함)

**Q: Autoheal이 작동하지 않는 것 같습니다.**
A: `docker compose logs autoheal`을 확인하세요. `Watching...` 메시지가 떠 있어야 하며, 대상 서비스에 `labels: - "autoheal=true"`가 설정되어 있어야 합니다.
