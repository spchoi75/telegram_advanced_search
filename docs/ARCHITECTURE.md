# Architecture v2: TeleSearch-KR

## 1. 시스템 구조 개요

### 1.1 상위 목적
기존 CLI 기반 Telegram 메시지 검색 도구를 GUI 데스크톱 앱과 모바일 웹으로 확장하여, 다양한 플랫폼에서 일관된 검색 경험 제공

### 1.2 컨텍스트 요약

```
┌─────────────────────────────────────────────────────────────────────┐
│                           사용자                                    │
└───────────┬─────────────────────────────────┬───────────────────────┘
            │ (Mac/PC)                        │ (모바일)
            ▼                                 ▼
┌───────────────────────────┐       ┌─────────────────────────┐
│   Tauri Desktop App       │       │   Vercel 웹앱           │
│   ┌───────────────────┐   │       │   (Next.js)             │
│   │ React UI          │   │       └───────────┬─────────────┘
│   └─────────┬─────────┘   │                   │
│             │ IPC         │                   │
│   ┌─────────▼─────────┐   │                   │
│   │ Rust Backend      │   │                   │
│   └─────────┬─────────┘   │                   │
│             │ subprocess  │                   │
│   ┌─────────▼─────────┐   │                   │
│   │ Python Scripts    │   │                   │
│   │ - indexer.py      │   │                   │
│   │ - searcher.py     │   │                   │
│   │ - chat_list.py    │   │                   │
│   │ - sync.py         │   │                   │
│   └─────────┬─────────┘   │                   │
│             │             │                   │
│   ┌─────────▼─────────┐   │   ┌─────────────────────────────┐
│   │ SQLite (로컬)     │───┼──►│      Supabase               │
│   │ FTS5 trigram      │   │   │      PostgreSQL + pg_trgm   │
│   └───────────────────┘   │   └──────────────┬──────────────┘
└───────────────────────────┘                  │
                                               │
            Telegram API ◄─────────────────────┘
```

### 1.3 시스템 경계
- **내부**: Tauri 앱, Python 스크립트, 로컬 SQLite, Vercel 웹앱
- **외부**: Telegram API, Supabase

---

## 2. 아키텍처 상위 구조 (컨테이너 뷰)

### 2.1 주요 컨테이너

| 컨테이너 | 책임 | 기술 |
|----------|------|------|
| **Tauri Desktop** | GUI 제공, Python 스크립트 실행 관리 | Tauri 2.0, React, TypeScript |
| **Python Scripts** | Telegram 연동, 검색 로직, 동기화 | Python 3.9+, Telethon |
| **SQLite DB** | 로컬 메시지 저장 + FTS5 검색 | SQLite 3 |
| **Supabase** | 클라우드 메시지 저장 + 원격 검색 | PostgreSQL + pg_trgm |
| **Vercel Web** | 모바일 검색 UI | Next.js 14 |

### 2.2 컨테이너 간 상호작용

```
Tauri UI ──(IPC)──► Rust Backend ──(subprocess)──► Python Scripts
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │ SQLite (로컬)   │
                                              └────────┬────────┘
                                                       │ sync
                                                       ▼
Vercel Web ──(HTTP)──► Supabase API ◄──────── Supabase DB
```

### 2.3 데이터 흐름 개요

**인덱싱 흐름**:
1. 사용자 → Tauri UI: 채팅방 선택 + 인덱싱 버튼 클릭
2. Tauri → Rust: IPC 호출 (start_indexing)
3. Rust → Python: subprocess 실행 (indexer.py --chat-id X)
4. Python → Telegram API: TakeoutClient로 메시지 수집
5. Python → SQLite: 배치 저장 (1,000개 단위)
6. Python → Supabase: 자동 동기화 (sync.py 호출)

**검색 흐름 (데스크톱)**:
1. 사용자 → Tauri UI: 검색어 입력
2. Tauri → Rust → Python: searcher.py --json 실행
3. Python → SQLite: FTS5 MATCH 쿼리
4. 결과 → UI 표시

**검색 흐름 (모바일)**:
1. 사용자 → Vercel 웹: 검색어 입력
2. Vercel → Supabase: pg_trgm 검색 쿼리
3. 결과 → UI 표시

**취소 흐름 (인덱싱/동기화)**:
1. 사용자 → Tauri UI: 취소 버튼 클릭
2. Tauri → Rust: IPC 호출 (cancel_indexing 또는 cancel_sync)
3. Rust: subprocess SIGTERM 전송
4. Python: 시그널 핸들러 → Takeout 세션 종료 / 롤백 수행
5. Rust → UI: "cancelled" 상태 이벤트 emit

---

## 3. 상세 구조 (컴포넌트 뷰)

### 3.1 Tauri Desktop 내부 구조

```
desktop/
├── src/                        # React Frontend
│   ├── components/
│   │   ├── ChatSelector.tsx    # 채팅방 드롭다운
│   │   ├── IndexingPanel.tsx   # 인덱싱 버튼 + 진행률 + 취소
│   │   ├── ProgressBar.tsx     # 공통 진행률 바 (백분율, ETA)
│   │   ├── SearchBar.tsx       # 검색 입력
│   │   ├── SearchOptions.tsx   # 결과 수, 기간 옵션
│   │   └── ResultList.tsx      # 검색 결과 목록
│   ├── hooks/
│   │   ├── useTauriCommand.ts  # IPC 래퍼
│   │   └── useSearch.ts        # 검색 상태 관리
│   ├── App.tsx
│   └── main.tsx
└── src-tauri/
    └── src/
        ├── main.rs             # Tauri 진입점
        └── commands/
            ├── mod.rs
            ├── indexing.rs     # start_indexing, get_progress
            ├── search.rs       # run_search
            └── chat_list.rs    # get_chat_list
```

**의존 방향**:
```
React Components → Hooks → Tauri Commands (Rust) → Python Scripts
```

### 3.2 Python Scripts 내부 구조

```
telegram_advanced_search/
├── indexer.py          # 기존 유지 (변경 없음)
├── searcher.py         # --json 플래그 추가
├── chat_list.py        # 신규: 채팅방 목록 조회
├── sync.py             # 신규: SQLite → Supabase 동기화
└── lib/
    ├── __init__.py
    ├── db.py           # SQLite 연결 공통화
    ├── telegram.py     # Telethon 클라이언트 공통화
    └── supabase.py     # Supabase 연결
```

**의존 방향**:
```
indexer.py, searcher.py, chat_list.py, sync.py
           │
           ▼
        lib/ (공통 모듈)
           │
           ▼
    외부 라이브러리 (Telethon, sqlite3, supabase-py)
```

### 3.3 Vercel Web 내부 구조

```
web/
├── app/
│   ├── layout.tsx
│   ├── page.tsx            # 검색 메인 페이지
│   └── api/
│       └── search/
│           └── route.ts    # Supabase 검색 API
├── components/
│   ├── SearchBar.tsx
│   └── ResultList.tsx
└── lib/
    └── supabase.ts
```

---

## 4. 아키텍처 결정 기록 (ADR Summary)

### ADR-001: 데스크톱 프레임워크 선택

**고려한 대안**:
1. Electron + Node.js
2. Tauri + Rust
3. PyQt / PySide

**선택**: Tauri + Rust

**선택 근거**:
- 번들 크기: Tauri 3-5MB vs Electron 200MB+
- 메모리 사용량: Tauri가 훨씬 적음
- Python 연동: 두 프레임워크 모두 subprocess로 동일하게 가능
- 보안: Rust 기반으로 메모리 안전성 보장

**트레이드오프**: Rust 학습 필요, 하지만 Python 핵심 로직은 그대로 유지

---

### ADR-002: 이중 저장소 구조

**고려한 대안**:
1. Supabase만 사용 (클라우드 전용)
2. SQLite만 사용 (로컬 전용)
3. SQLite + Supabase (하이브리드)

**선택**: SQLite + Supabase 하이브리드

**선택 근거**:
- 로컬 SQLite FTS5: 검색 속도 < 100ms (최고 성능)
- Supabase: 모바일 접근성 확보
- 자동 동기화로 데이터 일관성 유지

**트레이드오프**: 동기화 로직 추가 필요, 데이터 중복 저장

---

### ADR-003: 기존 코드 유지 전략

**고려한 대안**:
1. 전체 재작성 (Rust 또는 TypeScript로)
2. 기존 Python 코드 래핑
3. 기존 코드 수정 최소화 + 확장

**선택**: 기존 코드 수정 최소화 + 확장

**선택 근거**:
- indexer.py, searcher.py는 이미 검증된 로직
- JSON 출력 플래그 추가만으로 GUI 연동 가능
- 리스크 최소화, 개발 속도 향상

**트레이드오프**: Python subprocess 오버헤드 (무시 가능 수준)

---

## 5. 파일 구조 (최종)

```
telegram_advanced_search/
├── archive/                    # v1 문서 보관
│   ├── prd_v1.md
│   ├── architecture_v1.md
│   ├── wbs_v1.md
│   ├── CLAUDE_v1.md
│   └── README_v1.md
├── docs/
│   ├── PRD.md                  # PRD v2
│   └── ARCHITECTURE.md         # Architecture v2
├── indexer.py                  # 기존 유지
├── searcher.py                 # --json 추가
├── chat_list.py                # 신규
├── sync.py                     # 신규
├── lib/                        # 공통 모듈
│   ├── __init__.py
│   ├── db.py
│   ├── telegram.py
│   └── supabase.py
├── requirements.txt
├── .env.example
├── README.md
├── CLAUDE.md
├── desktop/                    # Tauri 앱
│   ├── src/
│   ├── src-tauri/
│   ├── package.json
│   └── tauri.conf.json
└── web/                        # Vercel 웹
    ├── app/
    ├── components/
    ├── lib/
    ├── package.json
    └── vercel.json
```
