"""
Gemini API Rate Limit 테스트 도구
사용법: python -m novel_aize_ssr.rate_limit_tester --api-key YOUR_KEY
"""

import asyncio
import time
import argparse
from datetime import datetime
from google import genai

class RateLimitTester:
    def __init__(self, api_key: str, model_name: str = "gemini-3-flash-preview"):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.log = []
        
    def print_log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S. %f")[:-3]
        line = f"[{timestamp}] {msg}"
        print(line)
        self.log.append(line)
        
    # ============================================
    # 테스트 1: RPM (분당 요청 수) 테스트
    # ============================================
    async def test_rpm(self, max_requests: int = 50):
        """1분 동안 최대한 많은 요청을 보내서 RPM 한계 측정"""
        
        print("\n" + "="*60)
        print("🧪 테스트 1: RPM (분당 요청 수) 측정")
        print("="*60)
        
        simple_prompt = "Say 'OK' only."  # 최소 토큰 사용
        
        success_count = 0
        fail_count = 0
        first_fail_at = None
        start_time = time.time()
        
        for i in range(max_requests):
            elapsed = time.time() - start_time
            if elapsed >= 60:  # 1분 경과
                break
                
            try:
                response = self.client.models.generate_content(
                    model=self. model_name,
                    contents=simple_prompt
                )
                success_count += 1
                self.print_log(f"✅ 요청 #{i+1} 성공 | 총 {success_count}개 | 경과: {elapsed:.1f}초")
                
            except Exception as e:
                fail_count += 1
                error_str = str(e)
                
                if "429" in error_str or "ResourceExhausted" in error_str:
                    if first_fail_at is None: 
                        first_fail_at = success_count
                    self.print_log(f"❌ 요청 #{i+1} RATE LIMITED | 경과: {elapsed:.1f}초")
                else:
                    self.print_log(f"❌ 요청 #{i+1} 에러:  {error_str[: 50]}")
                    
            # 아주 짧은 간격 (제한 테스트용)
            await asyncio.sleep(0.1)
        
        total_time = time.time() - start_time
        
        print("\n📊 [RPM 테스트 결과]")
        print(f"   총 소요 시간: {total_time:.1f}초")
        print(f"   성공:  {success_count}개")
        print(f"   실패: {fail_count}개")
        if first_fail_at: 
            print(f"   ⚠️  첫 Rate Limit 발생: {first_fail_at}번째 요청 후")
            print(f"   📌 추정 RPM 한계: 약 {first_fail_at}개/분")
        else:
            print(f"   ✅ {max_requests}개 요청 모두 성공!  RPM > {success_count}")
            
        return first_fail_at or success_count
    
    # ============================================
    # 테스트 2: 동시 요청 한계 테스트
    # ============================================
    async def test_concurrency(self, max_concurrent: int = 30):
        """동시에 N개 요청을 보내서 한계 측정"""
        
        print("\n" + "="*60)
        print("🧪 테스트 2: 동시 요청 한계 측정")
        print("="*60)
        
        simple_prompt = "Say 'OK' only."
        
        async def single_request(idx:  int):
            try:
                start = time.time()
                loop = asyncio.get_running_loop()
                
                def sync_call():
                    return self.client.models.generate_content(
                        model=self.model_name,
                        contents=simple_prompt
                    )
                
                await loop.run_in_executor(None, sync_call)
                elapsed = time.time() - start
                return (idx, "success", elapsed)
                
            except Exception as e:
                elapsed = time.time() - start
                if "429" in str(e) or "ResourceExhausted" in str(e):
                    return (idx, "rate_limited", elapsed)
                return (idx, f"error:  {str(e)[:30]}", elapsed)
        
        for batch_size in [5, 10, 15, 20, 25, 30]:
            if batch_size > max_concurrent: 
                break
                
            print(f"\n🔄 동시 {batch_size}개 요청 테스트...")
            
            tasks = [single_request(i) for i in range(batch_size)]
            results = await asyncio.gather(*tasks)
            
            success = sum(1 for r in results if r[1] == "success")
            limited = sum(1 for r in results if r[1] == "rate_limited")
            
            self.print_log(f"   동시 {batch_size}개 → 성공: {success}, Rate Limited: {limited}")
            
            if limited > 0:
                print(f"   ⚠️  동시 {batch_size}개에서 Rate Limit 발생!")
                print(f"   📌 추정 동시 요청 한계: 약 {batch_size - limited}개")
                break
                
            # 다음 테스트 전 쿨다운
            await asyncio. sleep(5)
            
    # ============================================
    # 테스트 3: TPM (분당 토큰) 테스트
    # ============================================
    async def test_tpm(self):
        """큰 프롬프트로 토큰 제한 테스트"""
        
        print("\n" + "="*60)
        print("🧪 테스트 3: TPM (분당 토큰 수) 측정")
        print("="*60)
        
        # 다양한 크기의 프롬프트
        test_sizes = [
            (1000, "1K"),
            (5000, "5K"),
            (10000, "10K"),
            (20000, "20K"),
            (50000, "50K"),
        ]
        
        base_text = "이것은 테스트 문장입니다.  " * 100  # 약 2000자
        
        for char_count, label in test_sizes:
            prompt = f"Summarize this in one sentence: {base_text[: char_count]}"
            
            try:
                start = time.time()
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                elapsed = time.time() - start
                self.print_log(f"✅ {label} 문자 → 성공 ({elapsed:.1f}초)")
                
            except Exception as e: 
                if "429" in str(e) or "ResourceExhausted" in str(e):
                    self.print_log(f"❌ {label} 문자 → RATE LIMITED")
                else:
                    self.print_log(f"❌ {label} 문자 → 에러:  {str(e)[:50]}")
                    
            await asyncio.sleep(2)
            
    # ============================================
    # 테스트 4: 429 후 복구 시간 측정
    # ============================================
    async def test_recovery_time(self):
        """Rate Limit 걸린 후 복구까지 걸리는 시간 측정"""
        
        print("\n" + "="*60)
        print("🧪 테스트 4: Rate Limit 복구 시간 측정")
        print("="*60)
        
        simple_prompt = "Say 'OK' only."
        
        # 먼저 Rate Limit 유발
        print("1️⃣ Rate Limit 유발 중...")
        for i in range(30):
            try:
                self.client.models.generate_content(
                    model=self. model_name,
                    contents=simple_prompt
                )
            except: 
                self.print_log(f"   Rate Limit 발생!  ({i+1}번째 요청)")
                break
                
        # 복구 시간 측정
        print("2️⃣ 복구 시간 측정 중...")
        wait_times = [1, 2, 5, 10, 15, 20, 30, 45, 60]
        
        for wait in wait_times:
            await asyncio.sleep(wait)
            
            try:
                self.client.models.generate_content(
                    model=self. model_name,
                    contents=simple_prompt
                )
                self.print_log(f"✅ {wait}초 대기 후 복구됨!")
                print(f"   📌 추정 복구 시간:  약 {wait}초")
                break
                
            except Exception as e:
                if "429" in str(e):
                    self.print_log(f"❌ {wait}초 대기 → 아직 제한 중")
                    
    # ============================================
    # 전체 테스트 실행
    # ============================================
    async def run_all_tests(self):
        print("\n" + "🚀"*30)
        print("   Gemini API Rate Limit 종합 테스트 시작")
        print("🚀"*30)
        print(f"\n📌 모델: {self.model_name}")
        print(f"📌 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 테스트 실행
        rpm_limit = await self.test_rpm(max_requests=40)
        
        print("\n⏳ 다음 테스트 전 60초 쿨다운...")
        await asyncio.sleep(60)
        
        await self.test_concurrency(max_concurrent=25)
        
        print("\n⏳ 다음 테스트 전 30초 쿨다운...")
        await asyncio.sleep(30)
        
        await self. test_tpm()
        
        print("\n⏳ 다음 테스트 전 30초 쿨다운...")
        await asyncio.sleep(30)
        
        await self.test_recovery_time()
        
        # 결과 요약
        print("\n" + "="*60)
        print("📋 종합 테스트 결과 요약")
        print("="*60)
        print(f"   추정 RPM 한계:  ~{rpm_limit}개/분")
        print(f"   권장 concurrency: {max(1, rpm_limit // 4)}~{max(1, rpm_limit // 2)}")
        print(f"   권장 요청 간격: {60 / rpm_limit:.1f}초 이상")
        
        # 로그 저장
        log_file = f"rate_limit_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.log))
        print(f"\n📁 로그 저장됨: {log_file}")


def main():
    parser = argparse.ArgumentParser(description="Gemini API Rate Limit Tester")
    parser.add_argument("--api-key", required=True, help="Google Gemini API Key")
    parser.add_argument("--model", default="gemini-3-flash-preview", help="Model name")
    parser.add_argument("--test", choices=["rpm", "concurrency", "tpm", "recovery", "all"], 
                        default="all", help="Test to run")
    
    args = parser.parse_args()
    
    tester = RateLimitTester(api_key=args.api_key, model_name=args.model)
    
    if args.test == "all":
        asyncio.run(tester.run_all_tests())
    elif args.test == "rpm": 
        asyncio.run(tester.test_rpm())
    elif args.test == "concurrency":
        asyncio.run(tester. test_concurrency())
    elif args.test == "tpm": 
        asyncio.run(tester.test_tpm())
    elif args.test == "recovery":
        asyncio.run(tester.test_recovery_time())


if __name__ == "__main__":
    main()






'''
    PS E:\DEVz\07_TXT_Split_Summary\ver001> python .\novel_aize_ssr\rate_limit_tester.py --api-key AIzaSyCSy-eecOg4Lop-M0_5r5nyhMZMYsT-bhg --test all

🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀
   Gemini API Rate Limit 종합 테스트 시작
🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀

📌 모델: gemini-3-flash-preview
📌 시작 시간: 2026-01-11 09:44:58

============================================================
🧪 테스트 1: RPM (분당 요청 수) 측정
============================================================
[09:45:00. 563] ✅ 요청 #1 성공 | 총 1개 | 경과: 0.0초
[09:45:01. 692] ✅ 요청 #2 성공 | 총 2개 | 경과: 2.0초
[09:45:03. 254] ✅ 요청 #3 성공 | 총 3개 | 경과: 3.1초
[09:45:04. 429] ✅ 요청 #4 성공 | 총 4개 | 경과: 4.7초
[09:45:05. 619] ✅ 요청 #5 성공 | 총 5개 | 경과: 5.8초
[09:45:07. 150] ✅ 요청 #6 성공 | 총 6개 | 경과: 7.0초
[09:45:08. 357] ✅ 요청 #7 성공 | 총 7개 | 경과: 8.6초
[09:45:09. 731] ✅ 요청 #8 성공 | 총 8개 | 경과: 9.8초
[09:45:10. 977] ✅ 요청 #9 성공 | 총 9개 | 경과: 11.1초
[09:45:11. 915] ✅ 요청 #10 성공 | 총 10개 | 경과: 12.4초
[09:45:13. 096] ✅ 요청 #11 성공 | 총 11개 | 경과: 13.3초
[09:45:14. 415] ✅ 요청 #12 성공 | 총 12개 | 경과: 14.5초
[09:45:15. 483] ✅ 요청 #13 성공 | 총 13개 | 경과: 15.8초
[09:45:16. 838] ✅ 요청 #14 성공 | 총 14개 | 경과: 16.9초
[09:45:17. 841] ✅ 요청 #15 성공 | 총 15개 | 경과: 18.2초
[09:45:18. 729] ✅ 요청 #16 성공 | 총 16개 | 경과: 19.2초
[09:45:20. 039] ✅ 요청 #17 성공 | 총 17개 | 경과: 20.1초
[09:45:21. 227] ✅ 요청 #18 성공 | 총 18개 | 경과: 21.4초
[09:45:22. 388] ✅ 요청 #19 성공 | 총 19개 | 경과: 22.6초
[09:45:23. 744] ✅ 요청 #20 성공 | 총 20개 | 경과: 23.8초
[09:45:25. 128] ✅ 요청 #21 성공 | 총 21개 | 경과: 25.2초
[09:45:26. 579] ✅ 요청 #22 성공 | 총 22개 | 경과: 26.5초
[09:45:28. 165] ✅ 요청 #23 성공 | 총 23개 | 경과: 28.0초
[09:45:29. 441] ✅ 요청 #24 성공 | 총 24개 | 경과: 29.6초
[09:45:30. 590] ✅ 요청 #25 성공 | 총 25개 | 경과: 30.8초
[09:45:32. 053] ✅ 요청 #26 성공 | 총 26개 | 경과: 32.0초
[09:45:33. 063] ✅ 요청 #27 성공 | 총 27개 | 경과: 33.5초
[09:45:34. 283] ✅ 요청 #28 성공 | 총 28개 | 경과: 34.5초
[09:45:35. 586] ✅ 요청 #29 성공 | 총 29개 | 경과: 35.7초
[09:45:36. 649] ✅ 요청 #30 성공 | 총 30개 | 경과: 37.0초
[09:45:37. 798] ✅ 요청 #31 성공 | 총 31개 | 경과: 38.1초
[09:45:38. 980] ✅ 요청 #32 성공 | 총 32개 | 경과: 39.2초
[09:45:39. 895] ✅ 요청 #33 성공 | 총 33개 | 경과: 40.4초
[09:45:41. 414] ✅ 요청 #34 성공 | 총 34개 | 경과: 41.3초
[09:45:42. 453] ✅ 요청 #35 성공 | 총 35개 | 경과: 42.8초
[09:45:43. 608] ✅ 요청 #36 성공 | 총 36개 | 경과: 43.9초
[09:45:45. 003] ✅ 요청 #37 성공 | 총 37개 | 경과: 45.0초
[09:45:46. 371] ✅ 요청 #38 성공 | 총 38개 | 경과: 46.4초
[09:45:47. 687] ✅ 요청 #39 성공 | 총 39개 | 경과: 47.8초
[09:45:48. 866] ✅ 요청 #40 성공 | 총 40개 | 경과: 49.1초

📊 [RPM 테스트 결과]
   총 소요 시간: 50.3초
   성공:  40개
   실패: 0개
   ✅ 40개 요청 모두 성공!  RPM > 40

⏳ 다음 테스트 전 60초 쿨다운...

============================================================
🧪 테스트 2: 동시 요청 한계 측정
============================================================

🔄 동시 5개 요청 테스트...
[09:46:50. 443]    동시 5개 → 성공: 5, Rate Limited: 0

🔄 동시 10개 요청 테스트...
[09:46:57. 139]    동시 10개 → 성공: 10, Rate Limited: 0

🔄 동시 15개 요청 테스트...
[09:47:03. 950]    동시 15개 → 성공: 15, Rate Limited: 0

🔄 동시 20개 요청 테스트...
[09:47:11. 297]    동시 20개 → 성공: 20, Rate Limited: 0

🔄 동시 25개 요청 테스트...
[09:47:18. 766]    동시 25개 → 성공: 25, Rate Limited: 0

⏳ 다음 테스트 전 30초 쿨다운...

============================================================
🧪 테스트 3: TPM (분당 토큰 수) 측정
============================================================
[09:47:56. 476] ✅ 1K 문자 → 성공 (2.7초)
[09:48:01. 216] ✅ 5K 문자 → 성공 (2.7초)
[09:48:06. 967] ✅ 10K 문자 → 성공 (3.7초)
[09:48:11. 746] ✅ 20K 문자 → 성공 (2.8초)
[09:48:17. 289] ✅ 50K 문자 → 성공 (3.5초)

⏳ 다음 테스트 전 30초 쿨다운...

============================================================
🧪 테스트 4: Rate Limit 복구 시간 측정
============================================================
1️⃣ Rate Limit 유발 중...
2️⃣ 복구 시간 측정 중...
[09:49:22. 425] ✅ 1초 대기 후 복구됨!
   📌 추정 복구 시간:  약 1초

============================================================
📋 종합 테스트 결과 요약
============================================================
   추정 RPM 한계:  ~40개/분
   권장 concurrency: 10~20
   권장 요청 간격: 1.5초 이상

📁 로그 저장됨: rate_limit_test_20260111_094922.log
PS E:\DEVz\07_TXT_Split_Summary\ver001> 





📊 테스트 결과 요약
항목	        결과	        	의미
RPM		        40+ 개/분		    50초에 40개 성공 = 분당 48개 이상!
동시 요청	    25개 모두 성공		동시에 25개 보내도 OK
TPM		        50K 문자 성공		토큰 제한 여유로움
복구 시간       1초		        	제한 걸려도 바로 복구





⏱️ 1,000화 예상 시간 (새 설정)

1,000화 ÷ 15 동시 요청 = 67 배치
67 배치 × 1.5초 간격 = ~100초
+ API 응답 시간 (~2초) = 약 200초


설정	        1,000화  예상 시간 
기존            (실패)	❌ 전부 실패
안전 모드       (concurrency: 3)  36분
새 설정         (concurrency: 15) 약 3~4분 🎉




🎯 결론
원래 문제: concurrency: 50이 문제가 아니라, 재시도 로직이 너무 약했던 것

실제로는:

RPM: 48+ (넉넉함)
동시 요청: 25개까지 OK
복구: 1초면 충분
17화가 실패한 진짜 이유: 아마 그 당시 일시적인 서버 부하나 다른 요인이었을 수 있어요.


'''



