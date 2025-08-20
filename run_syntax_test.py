#!/usr/bin/env python3
"""
구문 수정 모듈 테스트 실행 스크립트
"""

import os
import sys
import asyncio

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def main():
    """메인 테스트 실행"""
    try:
        # 환경 변수 설정 (테스트용)
        os.environ['OPENAI_API_KEY'] = 'test-key-for-mock'
        os.environ['DEBUG'] = 'True'
        
        print("🧪 구문 수정 모듈 테스트 시작")
        print("-" * 50)
        
        # 테스트 스크립트 import 및 실행
        from test_syntax_pipeline import test_syntax_fixer_only, test_syntax_pipeline
        
        # 1. 구문 수정기 단독 테스트
        print("\n1️⃣ 구문 수정기 단독 테스트")
        await test_syntax_fixer_only()
        
        # 2. 전체 파이프라인 테스트
        print("\n2️⃣ 전체 파이프라인 테스트")
        await test_syntax_pipeline()
        
        print("\n✅ 모든 테스트 완료!")
        
    except ImportError as e:
        print(f"❌ 모듈 import 실패: {e}")
        print("필요한 의존성이 설치되어 있는지 확인하세요:")
        print("pip install -r requirements.txt")
        
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main()) 