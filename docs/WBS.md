# WBS v2: TeleSearch-KR Desktop & Mobile

## 문서 정보
- **기반 문서**: PRD v2, Architecture v2
- **작성일**: 2025-12-10
- **상태**: 작성 완료

---

## Phase 1: 개발 기반 작업

### 1.1 개발 환경 설정
- [x] 프로젝트 디렉터리 구조 재구성 (archive/, docs/, lib/, desktop/, web/)
- [x] Python 가상환경 생성 및 requirements.txt 업데이트
- [ ] Node.js/pnpm 환경 설정 (desktop, web용) - Phase 4, 5에서 진행
- [x] .env.example 업데이트 (Supabase 관련 변수 추가)
- [x] .gitignore 업데이트 (Tauri 빌드, node_modules 등)

### 1.2 코드 표준화 작업
- [x] Python: ruff 포맷터 설정 (pyproject.toml)
- [ ] TypeScript: ESLint + Prettier 설정 - Phase 4, 5에서 진행
- [ ] pre-commit hook 설정 - 선택사항

### 1.3 CI/CD 파이프라인 구축
- [x] GitHub Actions 워크플로우 정의 (.github/workflows/ci.yml)
- [x] Python 테스트 자동화 파이프라인
- [ ] TypeScript 빌드/테스트 파이프라인 - Phase 4, 5에서 진행
- [ ] Vercel 배포 연동 설정 - Phase 5에서 진행

---

## Phase 2: Python 확장 (lib 모듈화)

### 2.1 공통 모듈 생성 (lib/)
- [x] lib/__init__.py 생성
- [x] lib/db.py: SQLite 연결 공통화
  - get_connection() 함수
  - 기존 indexer.py, searcher.py의 DB 로직 추출
- [x] lib/telegram.py: Telethon 클라이언트 공통화
  - get_client() 함수
  - 세션 관리 로직 추출

### 2.2 채팅방 목록 조회 (chat_list.py) [F-001]
- [x] chat_list.py 신규 생성
- [x] Telethon으로 전체 대화 목록 조회 구현
- [x] JSON 출력 형식 구현 (id, name, type)
- [x] 예외 처리 (세션 없음, 네트워크 오류 + 3회 재시도)

### 2.3 검색 기능 확장 (searcher.py) [F-003]
- [x] --json 플래그 추가
- [x] --chat-id 필터 옵션 추가 (기존 기능)
- [x] JSON 출력 형식 구현 (count, elapsed_ms, results)
- [x] 기존 CLI 출력과 호환 유지

### 2.4 Supabase 동기화 (sync.py) [F-004]
- [x] lib/supabase.py: Supabase 연결 모듈
  - supabase-py 클라이언트 초기화
  - 환경 변수 기반 연결
- [x] sync.py 신규 생성
  - 마지막 동기화 ID 조회 로직
  - 1,000개 배치 UPSERT 구현
  - 진행률 출력
- [x] 예외 처리 (연결 실패, 네트워크 중단 시 부분 동기화)

### 2.5 Python 단위 테스트
- [x] tests/test_chat_list.py: JSON 형식 검증
- [x] tests/test_searcher.py: JSON 출력 검증 (22 tests passed)
- [x] tests/test_sync.py: 배치 UPSERT 검증

---

## Phase 3: Supabase 설정

### 3.1 Supabase 프로젝트 설정
- [x] Supabase 프로젝트 생성 (또는 기존 프로젝트 사용)
- [x] pg_trgm 확장 활성화
- [x] messages 테이블 생성 (PRD 3.2 스키마)
- [x] GIN 인덱스 생성 (text gin_trgm_ops)
- [x] 복합 인덱스 생성 (chat_id, date DESC)

### 3.2 RLS 정책 설정
- [x] anon key: SELECT 권한만 허용
- [x] service key: INSERT/UPDATE 권한 허용
- [x] RLS 정책 테스트 (sync.py 실행으로 검증)

### 3.3 환경 변수 설정
- [x] SUPABASE_URL 발급 및 설정
- [x] SUPABASE_ANON_KEY 발급 및 설정
- [x] SUPABASE_SERVICE_KEY 발급 및 설정

---

## Phase 4: Tauri Desktop 앱 [F-005]

### 4.1 Tauri 프로젝트 초기화
- [ ] desktop/ 디렉터리 생성
- [ ] Tauri 2.0 + React + TypeScript 프로젝트 생성
- [ ] tauri.conf.json 설정 (앱 이름, 번들 ID 등)
- [ ] Python 실행 경로 설정

### 4.2 Rust Backend (src-tauri/)
- [ ] commands/mod.rs: 커맨드 모듈 구조 생성
- [ ] commands/chat_list.rs: get_chat_list 커맨드
  - Python chat_list.py subprocess 호출
  - JSON 파싱 및 반환
- [ ] commands/indexing.rs: start_indexing, get_progress 커맨드
  - Python indexer.py subprocess 호출
  - 실시간 stdout 스트리밍
- [ ] commands/search.rs: run_search 커맨드
  - Python searcher.py --json subprocess 호출
  - 결과 JSON 반환

### 4.3 React Frontend (src/)
- [ ] hooks/useTauriCommand.ts: IPC 래퍼 훅
- [ ] hooks/useSearch.ts: 검색 상태 관리 훅
- [ ] components/ChatSelector.tsx: 채팅방 드롭다운
  - get_chat_list 연동
  - 타입(개인/그룹/채널) 표시
- [ ] components/IndexingPanel.tsx: 인덱싱 UI
  - 인덱싱 시작 버튼
  - 진행률 바 (실시간 업데이트)
- [ ] components/SearchBar.tsx: 검색 입력
  - Cmd+K 단축키 지원
  - 최소 3글자 검증
- [ ] components/SearchOptions.tsx: 검색 옵션
  - 결과 수 선택 (10/20/50)
  - 기간 필터 (선택사항)
- [ ] components/ResultList.tsx: 검색 결과
  - 결과 목록 렌더링
  - 클릭 시 t.me 링크 열기 (shell.open)
- [ ] App.tsx: 메인 레이아웃 조합

### 4.4 Desktop 통합 테스트
- [ ] 채팅방 목록 조회 → UI 표시 테스트
- [ ] 인덱싱 실행 → 진행률 표시 테스트
- [ ] 검색 실행 → 결과 표시 테스트
- [ ] 결과 클릭 → 브라우저 링크 열기 테스트

---

## Phase 5: Vercel 모바일 웹 [F-006]

### 5.1 Next.js 프로젝트 초기화
- [ ] web/ 디렉터리 생성
- [ ] Next.js 14 + TypeScript 프로젝트 생성
- [ ] Tailwind CSS 설정 (모바일 반응형)
- [ ] vercel.json 설정

### 5.2 Supabase 연동 (lib/)
- [ ] lib/supabase.ts: Supabase 클라이언트 초기화
  - createBrowserSupabaseClient 설정
  - anon key 기반 연결

### 5.3 검색 API (app/api/)
- [ ] app/api/search/route.ts: 검색 API 엔드포인트
  - pg_trgm ILIKE 검색 쿼리
  - 결과 수 제한 (limit)
  - 채팅방 필터 (선택)

### 5.4 검색 UI (app/, components/)
- [ ] app/layout.tsx: 기본 레이아웃
- [ ] app/page.tsx: 검색 메인 페이지
- [ ] components/SearchBar.tsx: 검색 입력 (터치 최적화)
- [ ] components/ResultList.tsx: 검색 결과 목록
  - 결과 클릭 시 t.me 링크 이동

### 5.5 Web 통합 테스트
- [ ] 검색어 입력 → Supabase 조회 테스트
- [ ] 결과 표시 → 링크 동작 테스트
- [ ] 모바일 반응형 UI 테스트

---

## Phase 6: 전체 통합 및 최종 검증

### 6.1 End-to-End 테스트
- [ ] 인덱싱 → 자동 동기화 흐름 검증
- [ ] 데스크톱 검색 → 결과 표시 → 링크 열기 검증
- [ ] 모바일 웹 검색 → Supabase 조회 검증

### 6.2 예외 상황 테스트
- [ ] 네트워크 끊김 상태에서 동기화 시도
- [ ] 3글자 미만 검색어 입력 처리
- [ ] 존재하지 않는 채팅방 ID로 인덱싱 시도

### 6.3 성능 검증
- [ ] 로컬 검색 < 100ms 확인
- [ ] 원격 검색 < 500ms 확인
- [ ] 채팅방 목록 조회 < 2s 확인
- [ ] 동기화 1,000건당 < 5s 확인

### 6.4 문서 최종화
- [ ] README.md 업데이트 (설치/실행 가이드)
- [ ] .env.example 최종 검토

---

## 의존 관계 요약

```
Phase 1 (개발 기반)
    ↓
Phase 2 (Python 확장) ←→ Phase 3 (Supabase 설정)
    ↓                         ↓
Phase 4 (Tauri Desktop)  Phase 5 (Vercel Web)
    ↓                         ↓
         Phase 6 (전체 통합)
```

---

## PRD-Architecture-WBS 매핑 검증

| PRD 기능 | Architecture 컴포넌트 | WBS Phase |
|----------|----------------------|-----------|
| F-001 채팅방 목록 | chat_list.py, ChatSelector.tsx | Phase 2.2, 4.3 |
| F-002 인덱싱 | indexer.py (기존), IndexingPanel.tsx | Phase 4.3 |
| F-003 검색 | searcher.py, SearchBar/ResultList | Phase 2.3, 4.3, 5.4 |
| F-004 동기화 | sync.py, lib/supabase.py | Phase 2.4, 3.1 |
| F-005 데스크톱 UI | Tauri Desktop 전체 | Phase 4 |
| F-006 모바일 웹 | Vercel Web 전체 | Phase 5 |
