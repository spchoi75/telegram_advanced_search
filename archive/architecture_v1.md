# Architecture: TeleSearch-KR

## 1. 시스템 구조 개요

### 상위 목적
텔레그램 메시지를 로컬 SQLite DB에 수집하고, FTS5 trigram 인덱싱을 통해 한국어 부분 일치 검색을 제공하는 CLI 도구.

### 컨텍스트 요약

```
┌─────────────────────────────────────────────────────────────┐
│                        사용자 (User)                         │
└─────────────────────┬───────────────────┬───────────────────┘
                      │ CLI               │ CLI
                      ▼                   ▼
              ┌───────────────┐   ┌───────────────┐
              │  indexer.py   │   │  searcher.py  │
              │  (수집기)      │   │  (검색기)      │
              └───────┬───────┘   └───────┬───────┘
                      │                   │
                      │ Telethon          │
                      ▼                   │
              ┌───────────────┐           │
              │ Telegram API  │           │
              │ (TakeoutClient)│          │
              └───────────────┘           │
                      │                   │
                      │ 저장              │ 조회
                      ▼                   ▼
              ┌─────────────────────────────┐
              │     SQLite (search.db)      │
              │  ┌─────────┐ ┌───────────┐  │
              │  │messages │ │fts_messages│ │
              │  └─────────┘ └───────────┘  │
              └─────────────────────────────┘
```

### 시스템 경계
- **내부**: indexer.py, searcher.py, SQLite DB
- **외부**: Telegram API (MTProto)

---

## 2. 아키텍처 상위 구조 (컨테이너 뷰)

### 주요 컨테이너

| 컨테이너 | 책임 | 기술 |
|----------|------|------|
| **indexer.py** | 텔레그램 메시지 수집 및 DB 저장 | Python, Telethon |
| **searcher.py** | CLI 검색 인터페이스 | Python, sqlite3 |
| **SQLite DB** | 메시지 저장 및 FTS5 검색 | SQLite 3 + FTS5 |
| **.env** | 설정 관리 | 환경 변수 |

### 컨테이너 간 상호작용

```
indexer.py ──(async)──► Telegram API
    │
    │ (sync write)
    ▼
SQLite DB ◄──(sync read)── searcher.py
```

### 데이터 흐름 개요

**인덱싱 흐름:**
```
1. 사용자 → CLI 실행 (python indexer.py --chat-id xxx)
2. indexer.py → Telegram API (TakeoutClient 세션)
3. Telegram API → indexer.py (메시지 스트림)
4. indexer.py → SQLite (1,000개 배치 INSERT)
5. SQLite Trigger → FTS5 테이블 자동 동기화
```

**검색 흐름:**
```
1. 사용자 → CLI 실행 (python searcher.py "검색어")
2. searcher.py → SQLite FTS5 MATCH 쿼리
3. SQLite → searcher.py (결과 반환)
4. searcher.py → 사용자 (포맷팅된 출력 + 링크)
```

---

## 3. 상세 구조 (컴포넌트 뷰)

### 3.1 indexer.py 내부 구조

```
indexer.py
├── Config Layer (설정)
│   ├── load_env()          # .env 로드
│   └── parse_args()        # CLI 인자 파싱
│
├── Telegram Layer (외부 연동)
│   ├── TelegramClient      # Telethon 클라이언트
│   ├── TakeoutClient       # Rate Limit 회피 세션
│   └── iter_messages()     # 메시지 순회
│
├── Processing Layer (데이터 처리)
│   ├── filter_text_messages()  # 텍스트만 필터링
│   ├── batch_collector()       # 1,000개 배치 수집
│   └── get_last_message_id()   # 증분 백업용
│
└── Storage Layer (저장)
    ├── init_db()           # 테이블 생성
    └── batch_insert()      # executemany 실행
```

**의존 방향:**
```
Config → Telegram → Processing → Storage
         (외부)      (도메인)     (인프라)
```

### 3.2 searcher.py 내부 구조

```
searcher.py
├── Config Layer (설정)
│   ├── load_env()          # .env 로드
│   └── parse_args()        # CLI 인자 파싱
│
├── Search Layer (검색 로직)
│   ├── build_query()       # FTS5 MATCH 쿼리 생성
│   └── execute_search()    # 쿼리 실행
│
├── Presentation Layer (출력)
│   ├── highlight_text()    # 검색어 하이라이트
│   ├── build_link()        # t.me 링크 생성
│   └── format_result()     # 결과 포맷팅
│
└── Storage Layer (DB 접근)
    └── connect_db()        # SQLite 연결
```

**의존 방향:**
```
Config → Search → Presentation
           ↓
        Storage
```

### 3.3 SQLite DB 구조

```
search.db
├── messages (테이블)
│   ├── id (PK)         # Message ID
│   ├── chat_id         # 채팅방 ID
│   ├── sender_id       # 발신자 ID
│   ├── date            # Unix Timestamp
│   └── text            # 메시지 본문
│
├── fts_messages (FTS5 가상 테이블)
│   └── text            # trigram 인덱싱
│
├── idx_messages_chat_date (인덱스)
│   └── (chat_id, date DESC)
│
└── messages_ai (트리거)
    └── INSERT → FTS5 자동 동기화
```

---

## 4. 아키텍처 결정 기록 (ADR Summary)

### ADR-001: 전체 구조 선택

**고려한 대안:**
1. **모듈형 패키지 구조** - src/indexer/, src/searcher/, src/db/ 분리
2. **단일 파일 구조** - 모든 기능을 하나의 main.py에 포함
3. **2-파일 분리 구조** - indexer.py, searcher.py 독립 실행

**선택:** 2-파일 분리 구조

**선택 근거:**
- PRD에서 명시적으로 indexer.py, searcher.py 분리 요구
- 각 파일이 독립 실행 가능 (단일 책임)
- 저사양 환경에서 불필요한 import 오버헤드 제거
- 프로젝트 규모가 작아 과도한 모듈화 불필요 (YAGNI)

**트레이드오프:**
- 공통 코드(DB 연결, 설정 로드) 중복 가능성 → 코드량이 적어 허용 가능

---

### ADR-002: 비동기 처리 전략

**고려한 대안:**
1. **완전 비동기** - aiosqlite + asyncio 전체 적용
2. **혼합 방식** - Telethon만 async, DB는 sync
3. **완전 동기** - Telethon의 sync wrapper 사용

**선택:** 혼합 방식

**선택 근거:**
- Telethon은 asyncio 기반이므로 async 필수
- SQLite 쓰기는 배치 단위(1,000개)이므로 sync로 충분
- aiosqlite 의존성 추가 불필요 (KISS)

**트레이드오프:**
- 대용량 배치 저장 시 잠깐의 블로킹 발생 → 1,000개 단위로 제한하여 최소화

---

### ADR-003: FTS5 동기화 방식

**고려한 대안:**
1. **트리거 기반 자동 동기화** - INSERT 시 트리거로 FTS 갱신
2. **수동 동기화** - 별도 rebuild 명령 실행
3. **External Content 없이 FTS5만 사용** - messages 테이블 없이 FTS5에 직접 저장

**선택:** 트리거 기반 자동 동기화 + External Content

**선택 근거:**
- External Content 사용으로 저장 공간 절약 (text 중복 저장 방지)
- 트리거로 일관성 자동 보장
- 증분 백업 시에도 FTS 인덱스 자동 갱신

**트레이드오프:**
- DELETE/UPDATE 시 추가 트리거 필요 → 현재 요구사항에 없으므로 미구현

---

## 5. 디렉토리 구조 (최종)

```
telegram_advanced_search/
├── indexer.py        # 데이터 수집기 (Telegram → DB)
├── searcher.py       # 검색 CLI (DB → 결과)
├── .env.example      # 환경변수 템플릿
├── .env              # 실제 환경변수 (gitignore)
├── requirements.txt  # Python 의존성
├── search.db         # SQLite DB (자동 생성, gitignore)
├── *.session         # Telethon 세션 파일 (자동 생성, gitignore)
├── prd.md            # 제품 요구사항 문서
└── architecture.md   # 이 문서
```
