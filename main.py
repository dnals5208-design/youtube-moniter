import time
import uiautomator2 as u2
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import sys

# ==========================================
# [설정]
# ==========================================
ADB_ADDR = "emulator-5554" 
KEYWORDS = ["해커스", "토익", "경찰공무원", "소방공무원", "공무원"]
REPEAT_COUNT = 10 

# ==========================================
# [기능] 구글 시트 연결 (초기화 포함)
# ==========================================
def get_worksheet():
    try:
        json_key = json.loads(os.environ['G_SHEET_KEY'])
        sheet_id = os.environ['G_SHEET_ID']
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json_key, scope)
        client = gspread.authorize(creds)
        sh = client.open_by_key(sheet_id)
        
        now = datetime.now()
        sheet_name = f"{now.year % 100}.{now.month}/{now.day}"
        header = ["날짜", "시간", "키워드", "회차", "광고여부", "비고"]
        
        try:
            worksheet = sh.worksheet(sheet_name)
            print(f"   ♻️ 기존 시트('{sheet_name}') 발견! 초기화합니다.")
            worksheet.clear() 
            worksheet.append_row(header)
        except:
            print(f"   🆕 새 시트('{sheet_name}')를 생성합니다.")
            worksheet = sh.add_worksheet(title=sheet_name, rows="1000", cols="20")
            worksheet.append_row(header)
            
        return worksheet
    except Exception as e:
        print(f"❌ 구글 시트 연결 실패: {e}")
        return None

def append_to_sheet(worksheet, data):
    if worksheet:
        try:
            row = [data["날짜"], data["시간"], data["키워드"], data["회차"], data["광고여부"], data["비고"]]
            worksheet.append_row(row)
            print("   📤 시트 저장 완료")
        except Exception as e:
            print(f"   ⚠️ 시트 저장 실패: {e}")

# ==========================================
# [기능] 유튜브 제어 (Watcher 제거 -> 직접 확인)
# ==========================================
def handle_popups_and_incognito(d):
    print("   🔨 초기 설정(팝업제거/시크릿모드) 진행 중...")
    
    # 1. 팝업 닫기 (단순 무식하게 직접 확인 - 가장 확실함)
    # 3번 정도 반복해서 혹시 늦게 뜨는 팝업도 잡음
    for _ in range(3):
        if d(text="Don't allow").exists:
            d(text="Don't allow").click()
            print("   -> 알림 거부 클릭")
        if d(text="허용 안함").exists:
            d(text="허용 안함").click()
        if d(text="Got it").exists:
            d(text="Got it").click()
        time.sleep(1)

    # 2. 시크릿 모드 진입
    print("   🕵️ 시크릿 모드 진입...")
    
    # 프로필 클릭 (좌표가 가장 빠름 - 우측 상단)
    d.click(0.92, 0.05) 
    time.sleep(2)
    
    # 시크릿 모드 메뉴 클릭
    if d(text="Turn on Incognito").exists:
        d(text="Turn on Incognito").click()
    elif d(text="시크릿 모드 사용").exists:
        d(text="시크릿 모드 사용").click()
    elif d(resourceId="com.google.android.youtube:id/incognito_item").exists:
        d(resourceId="com.google.android.youtube:id/incognito_item").click()
    else:
        # 혹시 메뉴가 안 열렸으면 다시 시도
        d.click(0.92, 0.05)
        time.sleep(1)
        if d(resourceId="com.google.android.youtube:id/incognito_item").exists:
             d(resourceId="com.google.android.youtube:id/incognito_item").click()
    
    time.sleep(3)
    
    # 시크릿 모드 진입 후 'Got it' 팝업 한 번 더 체크
    if d(text="Got it").exists: d(text="Got it").click()
    
    print("   ✅ 설정 완료")

def run_android_monitoring():
    # 1. 시트 준비
    ws = get_worksheet()
    
    print(f"📱 [MO] 에뮬레이터 연결...")
    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        # 2. 앱 실행
        print("   -> 🔴 YouTube APP 실행")
        d.app_stop("com.google.android.youtube")
        d.app_start("com.google.android.youtube")
        time.sleep(10) 
        
        # 3. 설정 진행
        handle_popups_and_incognito(d)

        # 4. 검색 반복
        for keyword in KEYWORDS:
            print(f"\n🔎 [{keyword}] 검색 시작")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush()
                print(f"   [{i}/{REPEAT_COUNT}] 진행 중...", end=" ")
                
                # 돋보기 클릭 (검색창이 없으면 클릭)
                if not d(resourceId="com.google.android.youtube:id/search_edit_text").exists:
                    d.click(0.9, 0.05)
                    time.sleep(1)
                
                # 검색어 입력
                d.send_keys(keyword)
                d.press("enter")
                
                # 로딩 대기
                time.sleep(10)
                
                # 스크롤
                d.swipe(500, 1500, 500, 500, 0.3) 
                time.sleep(2)
                
                # 화면 분석
                is_ad = "X"
                ad_text = "-"
                
                try:
                    xml = d.dump_hierarchy()
                    if 'text="광고"' in xml or 'text="Ad"' in xml or 'text="Sponsored"' in xml:
                        is_ad = "O"
                        lines = [line.split('"')[0] for line in xml.split('text="') if '"' in line]
                        for line in lines:
                            if len(line) > 1 and "광고" not in line and "분 전" not in line:
                                 if any(k in line for k in ["해커스", "에듀윌", "공단기", "메가", "경단기", "소방", "야나두", "시원스쿨"]):
                                     ad_text = line
                                     break
                        if ad_text == "-": ad_text = "광고발견"
                        print(f"🚨 발견! ({ad_text})")
                    else:
                        print(f"❌ 없음")
                except Exception as xml_e:
                    print(f"⚠️ 화면 읽기 실패(넘어감)")
                
                # 결과 저장
                result_data = {
                    "날짜": datetime.now().strftime('%Y-%m-%d'),
                    "시간": datetime.now().strftime('%H:%M:%S'),
                    "키워드": keyword,
                    "회차": i,
                    "광고여부": is_ad, 
                    "비고": f"{ad_text}"
                }
                append_to_sheet(ws, result_data)
                
                # 검색창 비우기 (다음 검색 준비)
                if d(description="Clear search query").exists:
                    d(description="Clear search query").click()
                elif d(resourceId="com.google.android.youtube:id/search_clear").exists:
                    d(resourceId="com.google.android.youtube:id/search_clear").click()
                else:
                    d.click(0.9, 0.05)
                    time.sleep(1)
                    d.clear_text()

    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    run_android_monitoring()
