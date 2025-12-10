#!/usr/bin/env python3
"""
TeleSearch-KR: Supabase Setup Script
Supabase 데이터베이스 초기 설정 스크립트

pg_trgm 확장, messages 테이블, 인덱스, RLS 정책을 생성합니다.
"""

import os
import sys

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()


def run_sql(client, sql: str, description: str):
    """Execute SQL via Supabase RPC."""
    print(f"  {description}...", end=" ")
    try:
        client.rpc("exec_sql", {"query": sql}).execute()
        print("✓")
        return True
    except Exception as e:
        # RPC가 없을 수 있음 - postgrest로는 DDL 실행 불가
        print(f"✗ ({e})")
        return False


def main():
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not service_key:
        print("❌ SUPABASE_URL과 SUPABASE_SERVICE_KEY가 .env에 필요합니다.")
        sys.exit(1)

    print(f"Supabase 프로젝트: {url}")
    print()

    # Supabase REST API로는 DDL을 직접 실행할 수 없음
    # SQL Editor에서 직접 실행해야 함
    print("=" * 60)
    print("Supabase SQL Editor에서 아래 SQL을 실행하세요:")
    print("https://supabase.com/dashboard/project/jqireianuolsourjlkek/sql")
    print("=" * 60)
    print()

    sql = """
-- 1. pg_trgm 확장 활성화
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 2. messages 테이블 생성
CREATE TABLE IF NOT EXISTS messages (
    id BIGINT PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    sender_id BIGINT,
    date TIMESTAMPTZ NOT NULL,
    text TEXT NOT NULL,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. GIN 인덱스 생성 (한국어 부분 검색용)
CREATE INDEX IF NOT EXISTS idx_messages_text_gin
ON messages USING GIN (text gin_trgm_ops);

-- 4. 복합 인덱스 생성 (채팅방별 날짜순 조회용)
CREATE INDEX IF NOT EXISTS idx_messages_chat_date
ON messages (chat_id, date DESC);

-- 5. RLS 활성화
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- 6. RLS 정책: anon은 SELECT만
CREATE POLICY "Allow anonymous read access"
ON messages FOR SELECT
TO anon
USING (true);

-- 7. RLS 정책: service_role은 모든 작업
CREATE POLICY "Allow service role full access"
ON messages FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- 8. 설정 확인
SELECT
    'pg_trgm' as extension,
    EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') as enabled;
"""

    print(sql)
    print()
    print("=" * 60)
    print()

    # 연결 테스트
    print("연결 테스트 중...")
    try:
        client = create_client(url, service_key)
        # 간단한 쿼리로 연결 확인
        result = client.table("messages").select("id").limit(1).execute()
        print("✓ Supabase 연결 성공")
        print(f"  messages 테이블 존재: 데이터 {len(result.data)}건")
    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg or "relation" in error_msg:
            print("✗ messages 테이블이 없습니다. 위 SQL을 먼저 실행하세요.")
        else:
            print(f"✗ 연결 실패: {e}")


if __name__ == "__main__":
    main()
