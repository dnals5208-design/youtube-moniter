import time
import uiautomator2 as u2
import pandas as pd
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# ==========================================
# [설정] 구글 시트 연동
# ==========================================
def upload_to_google_sheet(df):
    try:
        print("📊 구글 시트 업로드 시작...")
        
        # 1. 인증 정보 가져오기 (GitHub Secret에서 환경변수로 받음)
        json_key = json.loads(os.environ['G_SHEET_KEY'])
        sheet_id = os.environ['G_SHEET_ID']
        
        # 2. 구글 시트 접속
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json_key, scope)
        client = gspread.authorize(creds)
        
        # 3. 스프레드시트 열기
        sh = client.open_by_key(sheet_id)
        
        # 4. 시트(탭) 이름 생성 (예: 26.2/1)
        now = datetime.now()
        # 0을 뺀 포맷을 위해 포맷팅 사용 (윈도우/리눅스 호환)
        sheet_name = f"{now.year % 100}.{now.month}/{now.day}"
        
        # 5. 이미 해당 날짜 시트가 있는지 확인
        try:
            worksheet = sh.worksheet(sheet_name)
            print(f"   ℹ️ '{sheet_name}' 시트가 이미 존재합니다. 내용을 덮어씁니다.")
            worksheet.clear() # 기존 내용 삭제
        except:
            # 없으면 새로 생성 (행/열 넉넉하게)
            worksheet = sh.add_worksheet(title=sheet_name, rows="100", cols="20")
            print(f"   ✅ '{sheet_name}' 시트 신규 생성 완료")
            
        # 6. 데이터 업로드
        # 헤더 포함해서 리스트 형태로 변환
        data = [df.columns.values.tolist()] + df.values.tolist()
        worksheet.update(data)
        
        print("🎉 구글 시트 업로드 성공!")
        
    except Exception as e:
        print(f"❌ 구글 시트 업로드 실패: {e}")

# ==========================================
# [본문] 크롤링 로직
# ==========================================
ADB_ADDR = "emulator-5554" 
KEYWORDS = ["해커스", "토익", "경찰공무원", "소방공무원", "공무원"]

def run_android_monitoring():
    results = []
    print(f"📱 [MO] 안드로이드 에뮬레이터 연결 시도...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        print(f"   -> 연결 성공! 모델: {d.info.get('model')}")
        
        print("   -> 유튜브 실행 중...")
        d.app_start("com.android.chrome")
        time.sleep(5)
        
        for keyword in KEYWORDS:
            print(f" >> 검색: {keyword}")
            search_url = f"https://m.youtube.com/results?search_query={keyword}"
            d.shell(f'am start -a android.intent.action.VIEW -d "{search_url}"')
            time.sleep(7)
            
            xml = d.dump_hierarchy()
            
            is_ad = "X"
            if 'text="광고"' in xml or 'text="Ad"' in xml or 'text="Sponsored"' in xml:
                is_ad = "O"
                print(f"   🚨 [{keyword}] 광고 뜸!")
            else:
                print(f"   [{keyword}] 광고 없음")
            
            results.append({
                "시간": datetime.now().strftime('%H:%M:%S'),
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
        # 엑셀 저장 대신 구글 시트 함수 호출
        upload_to_google_sheet(df)
    else:
        print("❌ 데이터 없음")
