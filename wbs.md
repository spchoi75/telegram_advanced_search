# WBS: TeleSearch-KR

> PRD와 Architecture 문서 기반으로 작성됨
> 각 Phase는 단일 컨텍스트 내에서 완료 가능한 크기로 분해됨

---

## Phase 1: 개발 환경 설정

### 1.1 프로젝트 초기화
- [x] Git 저장소 초기화 및 `.gitignore` 생성
  - `search.db`, `.env`, `*.session`, `__pycache__/` 제외
- [x] `requirements.txt` 생성
  - `telethon>=1.34.0`
  - `python-dotenv>=1.0.0`
- [x] `.env.example` 생성
  - `API_ID`, `API_HASH`, `PHONE`, `DEFAULT_CHAT_ID`, `DB_PATH`

### 1.2 디렉토리 구조 확립
- [x] 프로젝트 루트에 `indexer.py`, `searcher.py` 생성
- [x] 문서 파일 확인 (`prd.md`, `architecture.md`, `wbs.md`)

---

## Phase 2: 데이터베이스 계층 구현

### 2.1 DB 스키마 구현 (indexer.py 내부)
- [x] `init_db()` 함수 구현
  - `messages` 테이블 생성
  - `idx_messages_chat_date` 인덱스 생성
  - `fts_messages` FTS5 가상 테이블 생성 (`tokenize='trigram'`)
  - `messages_ai` INSERT 트리거 생성

### 2.2 DB 유틸리티 함수
- [x] `get_last_message_id(chat_id)` 함수 구현
  - 해당 채팅방의 마지막 저장된 Message ID 조회
  - 증분 백업용
- [x] `batch_insert(messages)` 함수 구현
  - `executemany`로 1,000개 단위 배치 INSERT

---

## Phase 3: indexer.py 구현

### 3.1 설정 계층
- [x] `load_env()` 함수 구현
  - `python-dotenv`로 `.env` 로드
  - `API_ID`, `API_HASH`, `PHONE`, `DEFAULT_CHAT_ID`, `DB_PATH` 파싱
- [x] `parse_args()` 함수 구현 (argparse)
  - `--chat-id`: 대상 채팅방 ID (선택, .env 기본값)
  - `--years`: 수집 기간 (기본값: 3)
  - `--db`: DB 경로 (기본값: ./search.db)

### 3.2 Telegram 계층
- [x] `TelegramClient` 초기화 및 인증 로직
  - 세션 파일 자동 생성
  - 최초 실행 시 인증 코드 입력 처리
- [x] `TakeoutClient` 세션 요청 로직
  - `TakeoutInitDelayError` 예외 처리 (대기 시간 출력 후 종료)
- [x] `iter_messages()` 래퍼 함수
  - `offset_date` 파라미터로 기간 제한
  - `min_id` 파라미터로 증분 백업

### 3.3 처리 계층
- [x] `filter_text_messages()` 함수 구현
  - `message.text`가 존재하는 메시지만 필터링
- [x] `batch_collector()` 제너레이터 구현
  - 1,000개 단위로 메시지 수집
  - 진행률 출력 (수집된 메시지 수)

### 3.4 메인 흐름
- [x] `async def main()` 구현
  - 설정 로드 → DB 초기화 → Telegram 연결 → 메시지 수집 → 배치 저장
- [x] `FloodWaitError` 예외 처리
  - `client.flood_sleep_threshold` 설정
- [x] 완료 메시지 출력 (총 수집 건수)

---

## Phase 4: searcher.py 구현

### 4.1 설정 계층
- [x] `load_env()` 함수 구현
  - `DB_PATH` 파싱
- [x] `parse_args()` 함수 구현 (argparse)
  - `query`: 검색어 (위치 인자, 필수)
  - `--limit`: 결과 개수 (기본값: 20)
  - `--chat-id`: 특정 채팅방 필터 (선택)

### 4.2 검색 계층
- [x] `build_query()` 함수 구현
  - FTS5 MATCH 쿼리 생성
  - `chat_id` 필터 조건 추가 (선택적)
  - `ORDER BY date DESC` 정렬
  - `LIMIT` 적용
- [x] `execute_search()` 함수 구현
  - SQLite 연결 및 쿼리 실행
  - 결과 반환 (id, chat_id, sender_id, date, text)

### 4.3 출력 계층
- [x] `highlight_text(text, keyword)` 함수 구현
  - 검색어 부분을 ANSI 색상으로 하이라이트
- [x] `build_link(chat_id, message_id)` 함수 구현
  - `https://t.me/c/{chat_id}/{message_id}` 형식 생성
  - 채널/그룹 ID 변환 처리 (음수 → 양수 변환)
- [x] `format_result()` 함수 구현
  - 날짜 (YYYY-MM-DD HH:MM)
  - 본문 (하이라이트 적용, 최대 200자)
  - 원본 링크

### 4.4 메인 흐름
- [x] `def main()` 구현
  - 설정 로드 → 인자 파싱 → 검색 실행 → 결과 출력
- [x] DB 파일 없음 예외 처리
- [x] 검색 결과 없음 메시지 처리
- [x] 검색 소요 시간 출력

---

## Phase 5: 통합 및 마무리

### 5.1 통합 테스트
- [ ] indexer.py 실행 테스트
  - Telegram 인증 흐름 확인
  - 메시지 수집 및 DB 저장 확인
- [ ] searcher.py 실행 테스트
  - 한국어 부분 검색 확인 ('그램' → '텔레그램')
  - 결과 링크 정상 동작 확인

### 5.2 예외 상황 테스트
- [ ] 증분 백업 테스트 (indexer.py 재실행)
- [ ] 빈 검색 결과 처리 확인
- [ ] 잘못된 chat_id 입력 처리 확인

### 5.3 문서 정리
- [x] README.md 작성
  - 설치 방법, 사용법, 주의사항

---

## Phase 완료 체크리스트

| Phase | 상태 | 완료일 |
|-------|------|--------|
| Phase 1: 개발 환경 설정 | 완료 | 2025-12-10 |
| Phase 2: 데이터베이스 계층 | 완료 | 2025-12-10 |
| Phase 3: indexer.py | 완료 | 2025-12-10 |
| Phase 4: searcher.py | 완료 | 2025-12-10 |
| Phase 5: 통합 및 마무리 | 진행중 | - |

---

## 의존성 맵

```
Phase 1 ─────► Phase 2 ─────► Phase 3
                 │
                 └──────────► Phase 4
                                 │
Phase 3 + Phase 4 ──────────► Phase 5
```

- Phase 2는 Phase 1 완료 후 진행
- Phase 3, 4는 Phase 2 완료 후 병렬 진행 가능
- Phase 5는 Phase 3, 4 모두 완료 후 진행
