# PRD v2: TeleSearch-KR Desktop & Mobile

## 1. 문서 개요

### 1.1 목적
본 PRD는 기존 CLI 기반 TeleSearch-KR MVP를 **Tauri 데스크톱 앱 + 모바일 웹 검색**으로 확장하기 위한 단일 기준 문서(SSOT)이다.

### 1.2 범위
- 기존 핵심 기능(indexer.py, searcher.py)은 **변경 없이 유지**
- 새로운 GUI 래퍼와 클라우드 동기화 기능 추가
- 모바일은 **검색 전용** (인덱싱 미지원)

### 1.3 용어 정의
| 용어 | 정의 |
|------|------|
| 인덱싱 | Telegram 메시지를 수집하여 로컬 SQLite에 저장하는 작업 |
| 동기화 | 로컬 SQLite 데이터를 Supabase PostgreSQL로 업로드하는 작업 |
| FTS5 trigram | SQLite의 한국어 부분 검색을 지원하는 Full-Text Search 엔진 |

---

## 2. 기능 요구사항

### 2.1 채팅방 목록 조회 [F-001]

**입력**: Telegram 세션 (기존 .session 파일)

**처리**:
1. Telethon 클라이언트로 사용자의 전체 대화 목록 조회
2. 채팅방 ID, 이름, 타입(개인/그룹/채널) 추출
3. JSON 형식으로 반환

**출력**:
```json
{
  "chats": [
    {"id": -100123456789, "name": "채팅방명", "type": "supergroup"},
    {"id": 987654321, "name": "개인채팅", "type": "user"}
  ]
}
```

**예외 처리**:
| 예외 | 처리 |
|------|------|
| 세션 없음 | "Telegram 인증이 필요합니다" 메시지 + 인증 흐름 시작 |
| 네트워크 오류 | 3회 재시도 후 실패 메시지 |

---

### 2.2 메시지 인덱싱 [F-002]

**입력**:
- chat_id: 대상 채팅방 ID
- years: 수집 기간 (기본값: 3)

**처리**: 기존 indexer.py 로직 그대로 사용

**출력**:
- 실시간 진행률 (stdout으로 "Collected N messages..." 출력)
- 완료 시 총 메시지 수

**예외 처리**: 기존 indexer.py와 동일 (TakeoutInitDelayError, FloodWaitError 등)

**진행률 표시**:
- 실시간 메시지 수집 현황 (예: "1,234 / 5,000 메시지")
- 진행률 백분율 (%)
- 예상 남은 시간 (예: "~2분 30초")

**취소 기능**:
- 인덱싱 중 취소 버튼 제공
- 취소 시 Takeout 세션 정상 종료
- 부분 수집된 데이터는 롤백 (DB에서 삭제)

---

### 2.3 메시지 검색 [F-003]

**입력**:
- query: 검색어 (최소 3글자)
- limit: 결과 개수 (기본값: 20)
- chat_id: 필터링할 채팅방 (선택)
- output_format: "cli" | "json" (기본값: "cli")

**처리**: 기존 searcher.py + JSON 출력 옵션 추가

**출력 (JSON 모드)**:
```json
{
  "count": 5,
  "elapsed_ms": 23,
  "results": [
    {
      "id": 42,
      "chat_id": -100123456789,
      "date": "2024-03-15T14:32:00",
      "text": "텔레그램에서 재밌는...",
      "link": "https://t.me/c/123456789/42"
    }
  ]
}
```

**예외 처리**:
| 예외 | 처리 |
|------|------|
| 검색어 3글자 미만 | 에러 메시지 반환, 검색 실행 안 함 |
| DB 없음 | "인덱싱을 먼저 실행하세요" 메시지 |

---

### 2.4 Supabase 동기화 [F-004]

**입력**:
- 로컬 SQLite 경로
- Supabase 연결 정보

**처리**:
1. messages 테이블의 마지막 동기화 ID 조회
2. 새로운 메시지만 Supabase로 UPSERT
3. 1,000개 배치 단위 처리

**출력**: 동기화된 메시지 수

**트리거**: 인덱싱 완료 후 **자동 실행**

**예외 처리**:
| 예외 | 처리 |
|------|------|
| Supabase 연결 실패 | 로컬 저장은 성공, 동기화는 다음 기회로 연기 |
| 네트워크 중단 | 부분 동기화 허용, 재시도 시 이어서 진행 |

**진행률 표시**:
- 실시간 동기화 현황 (예: "1,000 / 5,432 메시지")
- 진행률 백분율 (%)
- 예상 남은 시간

**취소/롤백 기능**:
- 동기화 중 취소 버튼 제공
- 취소 시 부분 동기화 데이터 롤백 (Supabase에서 삭제)

---

### 2.5 데스크톱 UI [F-005]

**화면 구성**:

```
┌─────────────────────────────────────────────┐
│  TeleSearch-KR                    [─][□][×] │
├─────────────────────────────────────────────┤
│                                             │
│  채팅방: [▼ 전체 목록 드롭다운 ────────────]│
│                                             │
│  [인덱싱 시작]  진행률: ████████░░ 80%      │
│                                             │
│  ─────────────────────────────────────────  │
│                                             │
│  검색: [________________________] [검색]    │
│                                             │
│  옵션: 결과 수 [20▼]  기간 [전체▼]          │
│                                             │
│  ─────────────────────────────────────────  │
│                                             │
│  [1] 2024-03-15 14:32                       │
│  ...텔레그램에서 재밌는 영상을...           │
│  https://t.me/c/123456789/42                │
│                                             │
│  [2] 2024-03-10 09:15                       │
│  ...텔레그램 봇 만들기...                   │
│                                             │
└─────────────────────────────────────────────┘
```

**인터랙션**:
- Cmd+K: 검색창 포커스
- Enter: 검색 실행
- 결과 클릭: 시스템 브라우저에서 t.me 링크 열기

---

### 2.6 모바일 웹 검색 [F-006]

**화면 구성**: 데스크톱 UI의 검색 부분만 (인덱싱 제외)

**데이터 소스**: Supabase PostgreSQL (pg_trgm 검색)

**반응형**: 모바일 최적화 (터치 친화적)

---

## 3. 데이터 구조

### 3.1 로컬 SQLite (기존 유지)
```sql
messages (id, chat_id, sender_id, date, text)
fts_messages (text) -- FTS5 trigram
```

### 3.2 Supabase PostgreSQL
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE messages (
    id BIGINT PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    sender_id BIGINT,
    date TIMESTAMPTZ NOT NULL,
    text TEXT NOT NULL,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_text_gin ON messages USING GIN (text gin_trgm_ops);
CREATE INDEX idx_messages_chat_date ON messages (chat_id, date DESC);
```

### 3.3 데이터 역할 분류
| 데이터 | 역할 | 위치 |
|--------|------|------|
| messages | 원천(Source) | 로컬 SQLite |
| fts_messages | 파생(Derived) | 로컬 SQLite |
| Supabase messages | 캐시(Cache) | 클라우드 |

---

## 4. 환경 변수

```bash
# 기존 (유지)
API_ID=
API_HASH=
PHONE=
DEFAULT_CHAT_ID=
DB_PATH=./search.db

# 신규 추가
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...  # 동기화용
```

---

## 5. 성능 요구사항

| 기능 | 목표 |
|------|------|
| 로컬 검색 (SQLite FTS5) | < 100ms |
| 원격 검색 (Supabase) | < 500ms |
| 채팅방 목록 조회 | < 2s |
| 동기화 (1,000건당) | < 5s |

---

## 6. 보안 요구사항

| 항목 | 정책 |
|------|------|
| Telegram 세션 | .session 파일 로컬 저장, .gitignore 등록 |
| API 키 | .env 파일, .gitignore 등록 |
| Supabase RLS | anon key는 SELECT만, service key는 INSERT/UPDATE |

---

## 7. 테스트 기준

### 7.1 단위 테스트
- [ ] chat_list.py: 채팅방 목록 JSON 형식 검증
- [ ] searcher.py --json: JSON 출력 형식 검증
- [ ] sync.py: 배치 UPSERT 동작 검증

### 7.2 통합 테스트
- [ ] 인덱싱 → 자동 동기화 흐름
- [ ] 데스크톱 검색 → 결과 표시 → 링크 열기
- [ ] 모바일 웹 검색 → Supabase 조회

### 7.3 예외 테스트
- [ ] 네트워크 끊김 상태에서 동기화 시도
- [ ] 3글자 미만 검색어 입력
- [ ] 존재하지 않는 채팅방 ID로 인덱싱
