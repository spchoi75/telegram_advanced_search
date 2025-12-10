# TeleSearch-KR

텔레그램의 한국어 검색 한계를 극복하기 위한 개인용 메시지 검색 도구입니다.

SQLite FTS5의 trigram 토크나이저를 사용하여 한국어 부분 일치 검색을 지원합니다.

## 주요 기능

- **한국어 부분 검색**: '그램' 검색 시 '텔레그램' 매칭
- **조사 분리 지원**: '은/는/이/가' 등 조사가 붙어도 검색 가능
- **고속 검색**: 0.1초 이내 검색 결과 반환
- **증분 백업**: 이미 수집한 메시지는 건너뛰고 새 메시지만 수집
- **Rate Limit 회피**: Telegram TakeoutClient로 대량 다운로드 지원

## 설치

### 요구사항

- Python 3.9 이상
- Telegram API 키 (https://my.telegram.org)

### 설치 방법

```bash
# 저장소 클론
git clone <repository-url>
cd telegram_advanced_search

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
```

## 설정

### Telegram API 키 발급

1. https://my.telegram.org 접속
2. 로그인 후 "API development tools" 클릭
3. App 생성 (이름, 설명 입력)
4. `api_id`와 `api_hash` 복사

### .env 파일 설정

```bash
# Telegram API 설정
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890
PHONE=+821012345678

# 기본 대상 채팅방 ID (선택)
DEFAULT_CHAT_ID=

# 데이터베이스 경로 (선택)
DB_PATH=./search.db
```

### 채팅방 ID 확인 방법

1. Telegram 웹/데스크톱에서 채팅방 열기
2. URL에서 ID 확인:
   - 개인 채팅: `https://web.telegram.org/k/#-123456789` → `-123456789`
   - 채널/그룹: `https://web.telegram.org/k/#-100123456789` → `-100123456789`

또는 다른 Telegram 봇/도구를 사용하여 확인할 수 있습니다.

## 사용법

### 1. 메시지 인덱싱 (indexer.py)

채팅방의 메시지를 수집하여 로컬 DB에 저장합니다.

```bash
# 특정 채팅방 인덱싱
python indexer.py --chat-id -100123456789

# .env의 DEFAULT_CHAT_ID 사용
python indexer.py

# 수집 기간 지정 (기본: 3년)
python indexer.py --chat-id -100123456789 --years 5

# DB 경로 지정
python indexer.py --chat-id -100123456789 --db ./mydata.db
```

#### 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--chat-id` | 대상 채팅방 ID | .env의 DEFAULT_CHAT_ID |
| `--years` | 수집할 기간 (년) | 3 |
| `--db` | 데이터베이스 경로 | ./search.db |

#### 첫 실행 시

1. Telegram 인증 코드 입력 요청
2. 휴대폰으로 받은 코드 입력
3. 세션 파일 (`*.session`) 자동 생성
4. 이후 실행 시 자동 로그인

#### TakeoutInitDelayError 발생 시

텔레그램 보안 정책으로 Takeout 세션 승인 대기가 필요할 수 있습니다.
표시된 대기 시간 후 다시 실행하세요.

### 2. 메시지 검색 (searcher.py)

수집된 메시지에서 키워드를 검색합니다.

```bash
# 기본 검색 (최대 20개 결과)
python searcher.py "검색어"

# 결과 개수 조정
python searcher.py "검색어" --limit 50

# 특정 채팅방에서만 검색
python searcher.py "검색어" --chat-id -100123456789

# DB 경로 지정
python searcher.py "검색어" --db ./mydata.db
```

#### 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `query` | 검색어 (필수) | - |
| `--limit` | 최대 결과 개수 | 20 |
| `--chat-id` | 특정 채팅방 필터 | 전체 |
| `--db` | 데이터베이스 경로 | ./search.db |

#### 검색 결과 예시

```
Found 5 result(s) in 0.023s
============================================================

[1] 2024-03-15 14:32
...오늘 텔레그램에서 재밌는 영상을 봤어...
https://t.me/c/123456789/42

[2] 2024-03-10 09:15
...텔레그램 봇 만들기 프로젝트 시작...
https://t.me/c/123456789/38

============================================================
```

## 파일 구조

```
telegram_advanced_search/
├── indexer.py        # 메시지 수집기
├── searcher.py       # 검색 CLI
├── requirements.txt  # Python 의존성
├── .env.example      # 환경변수 템플릿
├── .env              # 실제 환경변수 (git 제외)
├── search.db         # SQLite DB (자동 생성, git 제외)
├── *.session         # Telethon 세션 (자동 생성, git 제외)
├── prd.md            # 제품 요구사항
├── architecture.md   # 아키텍처 문서
├── wbs.md            # 작업 분해 구조
└── README.md         # 이 문서
```

## 기술 스택

- **Python 3.9+**: 최신 SQLite FTS5 지원
- **Telethon**: 비동기 Telegram MTProto 클라이언트
- **SQLite FTS5**: Full-Text Search 엔진
- **Trigram Tokenizer**: 한국어 부분 일치 검색 지원

## 제한사항

- **검색어는 최소 3글자 이상** (trigram 토크나이저 특성)
- 텍스트 메시지만 인덱싱 (사진, 파일, 스티커 등 제외)
- 개인 사용 목적 (대량 배포 시 Telegram ToS 확인 필요)
- TakeoutClient 사용 시 계정당 1개 세션만 활성화 가능

## 문제 해결

### "Database not found" 오류

```bash
# indexer.py를 먼저 실행하여 DB 생성
python indexer.py --chat-id <your-chat-id>
```

### "API_ID and API_HASH are required" 오류

```bash
# .env 파일 확인
cat .env

# .env.example에서 복사 후 수정
cp .env.example .env
nano .env
```

### FloodWaitError 발생

API 요청이 너무 많을 때 발생합니다. 자동으로 대기 후 재시도됩니다.
`flood_sleep_threshold`가 60초로 설정되어 있어 60초 이하의 대기는 자동 처리됩니다.

### 검색 결과가 없을 때

1. 인덱싱이 완료되었는지 확인
2. 검색어 철자 확인
3. `--chat-id` 필터가 올바른지 확인

## 라이선스

MIT License
