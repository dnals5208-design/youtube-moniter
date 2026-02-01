import time
import uiautomator2 as u2
import pandas as pd
import os
from datetime import datetime

# GitHub Actions의 에뮬레이터는 기본적으로 이 주소를 씁니다.
ADB_ADDR = "emulator-5554" 
KEYWORDS = ["해커스", "토익", "경찰공무원", "소방공무원", "공무원"]

def run_android_monitoring():
    results = []
    print(f"📱 [MO] 안드로이드 에뮬레이터 연결 시도...")

    try:
        # 에뮬레이터가 켜질 때까지 잠시 대기
        os.system("adb wait-for-device")
        
        # 연결 시도
        d = u2.connect(ADB_ADDR)
        print(f"   -> 연결 성공! 모델: {d.info.get('model')}")
        
        # 유튜브 앱 실행
        # (GitHub 에뮬레이터에는 유튜브가 없을 수 있어 크롬 브라우저로 앱 모드 실행)
        print("   -> 유튜브(모바일 웹) 실행 중...")
        
        # 1. 크롬 실행
        d.app_start("com.android.chrome")
        time.sleep(5)
        
        # 2. 한국 IP 확인 (테스트용 - 나중에 주석 처리 가능)
        d.shell('am start -a android.intent.action.VIEW -d "https://myip.com"')
        time.sleep(5)

        for keyword in KEYWORDS:
            print(f" >> 검색: {keyword}")
            
            # 유튜브 검색 결과 URL로 바로 이동 (앱 검색과 동일 효과)
            search_url = f"https://m.youtube.com/results?search_query={keyword}"
            d.shell(f'am start -a android.intent.action.VIEW -d "{search_url}"')
            time.sleep(7) # 로딩 및 광고 대기
            
            # 화면 분석 (광고 배지 찾기)
            # dump_hierarchy()로 화면의 모든 텍스트를 가져옵니다.
            xml = d.dump_hierarchy()
            
            is_ad = "X"
            ad_text = "-"
            
            # 광고 식별 키워드
            if 'text="광고"' in xml or 'text="Ad"' in xml or 'text="Sponsored"' in xml:
                is_ad = "O"
                ad_text = "광고 발견됨"
                print(f"   🚨 [{keyword}] 광고 뜸!")
            else:
                print(f"   [{keyword}] 광고 없음")
            
            results.append({
                "날짜": datetime.now().strftime('%Y-%m-%d'),
                "키워드": keyword, 
                "광고여부": is_ad, 
                "비고": "GitHub Actions + Oracle Proxy"
            })

    except Exception as e:
        print(f"에러 발생: {e}")
    
    return results

if __name__ == "__main__":
    data = run_android_monitoring()
    if data:
        df = pd.DataFrame(data)
        df.to_excel("result.xlsx", index=False)
        print("✅ 엑셀 저장 완료")
    else:
        print("❌ 데이터 없음")
