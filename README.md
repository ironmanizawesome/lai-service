# LAI Service (working name: `laihub`)

모바일 우선 다중 사용자 LAI 분석 웹 서비스. 사용자가 폰으로 작물 영상을 올리면 [LingBot-Map](https://github.com/robbyant/lingbot-map) + `map-LAIpot` 파이프라인으로 LAI를 측정하고, 시계열·예측 그래프까지 제공한다.

> 자세한 설계: `c:\Users\ironm\.claude\plans\temporal-wondering-newt.md`

## 의존성

- **추론 엔진**: [LingBot-Map](https://github.com/robbyant/lingbot-map) (Apache 2.0) — 별도 repo로 분리되어 있고, 본 서비스는 그 출력(NPZ)과 `map-LAIpot` 함수를 호출한다.
- **웹 프레임워크**: Django 5 + Celery 5 + Redis
- **인증**: django-allauth (Google OAuth + email fallback)
- **시각화**: matplotlib (서버 측 PNG), Chart.js (시계열)

## 로컬 개발 셋업

1. **가상환경 생성 + 활성화** (Python 3.10+)
   ```powershell
   cd c:\Users\ironm\dev\lai-service
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

2. **의존성 설치**
   ```powershell
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **환경 변수 셋업**
   ```powershell
   copy .env.example .env
   # .env 파일을 열어서 DJANGO_SECRET_KEY 등을 채우기
   ```

4. **DB 마이그레이션 + 슈퍼유저** (M1 완료 후)
   ```powershell
   python manage.py migrate
   python manage.py createsuperuser
   ```

5. **개발 서버**
   ```powershell
   python manage.py runserver
   ```

## 마일스톤 진행 상황

- [x] 준비: repo 셋업 + 의존성 정의
- [ ] **M1**: Django 골격 + accounts(allauth) + 초기 모델 + 대시보드
- [ ] M2: 업로드 폼 + 더미 워커 + HTMX 폴링
- [ ] M3: 실 파이프라인 연결 (LingBot-Map 호출 + matplotlib 미리보기)
- [ ] M4: 시계열 + 예측 (TrendSnapshot + Chart.js + polyfit)
- [ ] M5: PWA + 모바일 QA
- [ ] M6: 공개 배포 (docker compose + 호스팅 + GPU worker)
- [ ] M7: 폴리시

## 라이선스

본 프로젝트는 Apache License 2.0 하에 배포된다 ([LICENSE](LICENSE)). LingBot-Map 의존성 또한 Apache 2.0.
