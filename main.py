import time
import uiautomator2 as u2
import pandas as pd
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# ==========================================
# [설정]
# ==========================================
ADB_ADDR = "emulator-5554" 
KEYWORDS = ["해커스", "토익", "경찰공무원", "소방공무원", "공무원"]
REPEAT_COUNT = 10 

def upload_to_google_sheet(df):
    try:
        print("📊 구글 시트 업로드 시작...")
        json_key = json.loads(os.environ['G_SHEET_KEY'])
        sheet_id = os.environ['G_SHEET_ID']
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json_key, scope)
        client = gspread.authorize(creds)
        sh = client.open_by_key(sheet_id)
        
        now = datetime.now()
        sheet_name = f"{now.year % 100}.{now.month}/{now.day}"
        try:
            worksheet = sh.worksheet(sheet_name)
        except:
            worksheet = sh.add_worksheet(title=sheet_name, rows="1000", cols="20")
            worksheet.append_row(df.columns.values.tolist())
        worksheet.append_rows(df.values.tolist())
        print("🎉 구글 시트 업로드 성공!")
    except Exception as e:
        print(f"❌ 구글 시트 업로드 실패: {e}")

def handle_youtube_popups(d):
    """유튜브 첫 실행 시 뜨는 팝업들(알림, 프리미엄 권유) 닫기"""
    print("   🔨 초기 팝업 정리 중...")
    
    # 1. 알림 허용 팝업 (허용 안함)
    if d(text="Don't allow").exists:
        d(text="Don't allow").click()
    if d(text="허용 안함").exists:
        d(text="허용 안함").click()
        
    time.sleep(2)
    
    # 2. 프리미엄 무료체험 팝업 (건너뛰기/닫기)
    # 버튼 텍스트가 다양해서 여러가지 시도
    skip_texts = ["Skip trial", "No thanks", "나중에", "건너뛰기", "닫기", "Dismiss"]
    for txt in skip_texts:
        if d(text=txt).exists:
            d(text=txt).click()
            print(f"   -> '{txt}' 클릭함")
            time.sleep(1)

def run_android_monitoring():
    results = []
    print(f"📱 [MO] 안드로이드 에뮬레이터 연결 시도...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        print(f"   -> 연결 성공! 모델: {d.info.get('model')}")
        
        # 1. 진짜 유튜브 앱 실행
        print("   -> 🔴 YouTube APP 실행 중...")
        # 기존에 켜져있으면 끄고 재실행
        d.app_stop("com.google.android.youtube")
        d.app_start("com.google.android.youtube")
        
        # 앱 로딩 대기 (앱은 크롬보다 무거워서 오래 기다려야 함)
        time.sleep(15)
        
        # 2. 초기 팝업 제거
        handle_youtube_popups(d)

        # 3. IP 확인 (브라우저 잠깐 켜서 확인)
        print("🌍 IP 확인을 위해 브라우저 잠시 실행...")
        d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io/json"')
        time.sleep(10)
        ip_dump = d.dump_hierarchy()
        if "KR" in ip_dump or "Korea" in ip_dump:
            print("   ✅ 한국 IP 확인됨")
        else:
            print("   ⚠️ 한국 IP 아님 (또는 로딩 실패)")
        
        # 다시 유튜브로 복귀
        d.app_start("com.google.android.youtube")
        time.sleep(5)

        # 4. 키워드 검색 반복
        for keyword in KEYWORDS:
            print(f"\n🔎 키워드 [{keyword}] 검색 시작")
            
            for i in range(1, REPEAT_COUNT + 1):
                print(f"   [{i}/{REPEAT_COUNT}] 검색 중...")
                
                # 앱 내 돋보기 버튼 클릭
                # (유튜브 앱 UI 요소 찾기)
                if d(description="Search").exists:
                    d(description="Search").click()
                elif d(resourceId="com.google.android.youtube:id/menu_item_search").exists:
                    d(resourceId="com.google.android.youtube:id/menu_item_search").click()
                else:
                    # 못 찾으면 좌표 클릭 (우측 상단)
                    d.click(0.9, 0.05)
                
                time.sleep(2)
                
                # 검색어 입력
                d.send_keys(keyword)
                time.sleep(1)
                d.press("enter")
                
                # 로딩 대기 (프록시라 넉넉히)
                time.sleep(15)
                
                # 스크롤 (광고 로딩 유도)
                d.swipe(500, 1500, 500, 500, 0.5)
                time.sleep(3)
                
                # 화면 분석
                xml = d.dump_hierarchy()
                
                is_ad = "X"
                ad_text = "-"
                
                # 앱 전용 광고 식별자 (앱에서는 '광고' 배지가 텍스트뷰로 존재)
                if 'text="광고"' in xml or 'text="Ad"' in xml or 'text="Sponsored"' in xml:
                    is_ad = "O"
                    # 광고주 추출 로직
                    lines = [line.split('"')[0] for line in xml.split('text="') if '"' in line]
                    for line in lines:
                        if len(line) > 1 and "광고" not in line and "분 전" not in line and ":" not in line:
                             if any(k in line for k in ["해커스", "에듀윌", "공단기", "메가"]):
                                 ad_text = line
                                 break
                    if ad_text == "-": ad_text = "광고발견(광고주미상)"
                    print(f"      🚨 앱 광고 뜸! ({ad_text})")
                else:
                    print(f"      ❌ 광고 없음")
                
                results.append({
                    "날짜": datetime.now().strftime('%Y-%m-%d'),
                    "시간": datetime.now().strftime('%H:%M:%S'),
                    "키워드": keyword,
                    "회차": i,
                    "광고여부": is_ad, 
                    "비고": f"YouTube APP / {ad_text}"
                })
                
                # 검색창 초기화를 위해 뒤로가기 두 번 (검색결과 -> 검색창 -> 홈)
                d.press("back")
                d.press("back")
                time.sleep(2)

    except Exception as e:
        print(f"에러 발생: {e}")
    
    return results

if __name__ == "__main__":
    data = run_android_monitoring()
    if data:
        df = pd.DataFrame(data)
        upload_to_google_sheet(df)
    else:
        print("❌ 데이터 없음")
