# PRD: TeleSearch-KR (Telegram Korean Searcher)

## 1. 프로젝트 개요

텔레그램의 취약한 한국어 검색 기능을 대체하기 위해, 사용자의 과거 대화 내역(Chat History)을 고속으로 추출하여 로컬 SQLite DB에 저장하고, 한국어에 특화된 Trigram 인덱싱을 통해 **0.1초 이내에 정확한 검색 결과**를 제공하는 개인용 검색 도구를 개발한다.

### 핵심 가치
- 한국어 조사('은/는/이/가') 분리 지원
- 부분 문자열 검색 ('그램' 검색 시 '텔레그램' 매칭)
- Rate Limit 회피를 통한 고속 다운로드

---

## 2. 핵심 기능 요구사항

### 2.1 indexer.py (데이터 수집기)

| 항목 | 요구사항 |
|------|----------|
| 라이브러리 | Telethon (Python) |
| 세션 방식 | **TakeoutClient 필수** - Rate Limit(FloodWait) 회피 |
| 수집 기간 | 과거 3년치 (설정 가능) |
| 배치 저장 | 1,000개 단위로 DB 저장 (I/O 최적화) |
| 증분 백업 | 최초 전체 수집 후, 마지막 Message ID 이후만 수집 |

**대상 채팅방 설정:**
- `.env`의 `DEFAULT_CHAT_ID` 사용 (기본값)
- CLI 인자 `--chat-id`로 오버라이드 가능

### 2.2 searcher.py (검색 인터페이스)

| 항목 | 요구사항 |
|------|----------|
| 인터페이스 | CLI 모드 |
| 검색 엔진 | SQLite FTS5 + trigram 토크나이저 |
| 결과 개수 | 기본 20개, `--limit` 옵션으로 조정 가능 |
| 결과 표시 | 검색어 하이라이트 + 원본 메시지 링크 |

**원본 링크 형식:** `https://t.me/c/{chat_id}/{message_id}`

---

## 3. 기술 스택

| 구분 | 기술 |
|------|------|
| 언어 | Python 3.9+ |
| 텔레그램 API | Telethon |
| 데이터베이스 | SQLite 3 (Python 내장 sqlite3) |
| 검색 엔진 | FTS5 + `tokenize='trigram'` |

### 환경 제약
- 저사양 VPS (1 CPU, 512MB RAM)에서도 동작해야 함

---

## 4. 데이터베이스 스키마

```sql
-- 메시지 테이블
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,           -- Message ID
    chat_id INTEGER NOT NULL,         -- 채팅방 ID
    sender_id INTEGER,                -- 발신자 ID
    date INTEGER NOT NULL,            -- Unix Timestamp
    text TEXT NOT NULL                -- 메시지 본문
);

-- 인덱스 (증분 백업용)
CREATE INDEX IF NOT EXISTS idx_messages_chat_date
ON messages(chat_id, date DESC);

-- FTS5 가상 테이블 (한국어 trigram 검색)
CREATE VIRTUAL TABLE IF NOT EXISTS fts_messages USING fts5(
    text,
    content='messages',
    content_rowid='id',
    tokenize='trigram'
);

-- FTS 트리거 (자동 동기화)
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO fts_messages(rowid, text) VALUES (new.id, new.text);
END;
```

---

## 5. 파일 구조

```
telegram_advanced_search/
├── indexer.py        # 데이터 수집기
├── searcher.py       # 검색 CLI
├── .env.example      # 환경변수 템플릿
├── .env              # 실제 환경변수 (git 제외)
├── requirements.txt  # Python 의존성
├── search.db         # SQLite 데이터베이스 (자동 생성)
└── prd.md            # 이 문서
```

---

## 6. 환경 변수

**.env.example:**
```bash
# Telegram API 설정 (https://my.telegram.org 에서 발급)
API_ID=your_api_id
API_HASH=your_api_hash
PHONE=+821012345678

# 기본 대상 채팅방 ID (선택)
DEFAULT_CHAT_ID=

# 데이터베이스 경로 (선택, 기본값: ./search.db)
DB_PATH=./search.db
```

---

## 7. CLI 사용법

### 인덱싱 (데이터 수집)

```bash
# 특정 채팅방 인덱싱
python indexer.py --chat-id 123456789

# .env의 DEFAULT_CHAT_ID 사용
python indexer.py

# 수집 기간 지정 (년 단위)
python indexer.py --chat-id 123456789 --years 5
```

### 검색

```bash
# 기본 검색 (최대 20개 결과)
python searcher.py "검색어"

# 결과 개수 조정
python searcher.py "검색어" --limit 50

# 특정 채팅방에서만 검색
python searcher.py "검색어" --chat-id 123456789
```

---

## 8. 구현 로직 가이드

### 8.1 indexer.py 흐름

```
1. Initialize
   └── Telethon 클라이언트 접속 및 인증
   └── Takeout 세션 요청

2. DB Setup
   └── search.db 연결
   └── 테이블 및 FTS5 가상 테이블 생성

3. Fetch Loop
   └── 지정된 채팅방(entity)으로 이동
   └── 마지막 저장된 Message ID 조회 (증분 백업)
   └── iter_messages로 메시지 순회
   └── 텍스트가 있는 메시지만 필터링
   └── 1,000개 단위로 executemany 실행

4. Complete
   └── 총 수집 건수 출력
   └── 세션 종료
```

### 8.2 searcher.py 흐름

```
1. Parse Arguments
   └── 검색어, --limit, --chat-id 파싱

2. Search
   └── FTS5 MATCH 쿼리 실행
   └── ORDER BY rank (관련도 순)

3. Format Output
   └── 날짜, 발신자, 본문 (하이라이트)
   └── 원본 링크 생성
```

---

## 9. 예외 처리

| 예외 | 처리 방법 |
|------|----------|
| `TakeoutInitDelayError` | 텔레그램 보안 정책상 대기 필요. 남은 시간 출력 후 종료. |
| `FloodWaitError` | `client.flood_sleep_threshold` 설정으로 자동 대기. |
| `ChatAdminRequiredError` | 권한 없는 채팅방. 오류 메시지 출력 후 스킵. |
| `sqlite3.IntegrityError` | 중복 메시지 ID. 무시하고 계속 진행. |

---

## 10. 향후 확장 가능성

- [ ] Telegram Bot 모드 (Saved Messages에서 검색)
- [ ] 여러 채팅방 동시 인덱싱
- [ ] 웹 UI 인터페이스
- [ ] 메시지 첨부파일(사진, 파일) 메타데이터 저장
