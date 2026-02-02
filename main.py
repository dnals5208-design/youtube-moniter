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
# [기능] 구글 시트 연결
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
        
        try:
            worksheet = sh.worksheet(sheet_name)
        except:
            worksheet = sh.add_worksheet(title=sheet_name, rows="1000", cols="20")
            header = ["날짜", "시간", "키워드", "회차", "광고여부", "비고"]
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
# [기능] 유튜브 제어
# ==========================================
def handle_popups_and_incognito(d):
    print("   🔨 초기 설정(시크릿모드) 진행 중...")
    
    # 팝업 닫기 (빠르게)
    d.watcher("POPUP").when(text="Don't allow").click(text="Don't allow")
    d.watcher("POPUP2").when(text="허용 안함").click(text="허용 안함")
    d.watcher("POPUP3").when(text="Got it").click(text="Got it")
    d.watcher.start() # 감시 시작
    
    time.sleep(3)

    # 시크릿 모드 진입
    print("   🕵️ 시크릿 모드 진입...")
    # 좌표로 누르는 게 가장 빠르고 정확함 (우측 상단 프로필)
    d.click(0.92, 0.05) 
    time.sleep(2)
    
    # '시크릿 모드 사용' 텍스트 찾기
    if d(text="Turn on Incognito").exists:
        d(text="Turn on Incognito").click()
    elif d(text="시크릿 모드 사용").exists:
        d(text="시크릿 모드 사용").click()
    elif d(resourceId="com.google.android.youtube:id/incognito_item").exists:
        d(resourceId="com.google.android.youtube:id/incognito_item").click()
    
    time.sleep(3)
    d.watcher.stop() # 감시 종료
    print("   ✅ 설정 완료")

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 에뮬레이터 연결...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        # 1. 유튜브 실행 (기존 앱 종료 후 깔끔하게 시작)
        print("   -> 🔴 YouTube APP 실행")
        d.app_stop("com.google.android.youtube")
        d.app_start("com.google.android.youtube")
        time.sleep(10) # 앱 로딩 대기 (15초 -> 10초 단축)
        
        # 2. 시크릿 모드 (IP 체크 삭제함)
        handle_popups_and_incognito(d)

        # 3. 키워드 검색 반복
        for keyword in KEYWORDS:
            print(f"\n🔎 [{keyword}] 검색 시작")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush()
                print(f"   [{i}/{REPEAT_COUNT}] 진행 중...", end=" ")
                
                # 돋보기 클릭 (좌표가 제일 빠름)
                if not d(resourceId="com.google.android.youtube:id/search_edit_text").exists:
                    d.click(0.9, 0.05)
                    time.sleep(1)
                
                # 검색어 입력
                d.send_keys(keyword)
                d.press("enter")
                
                # ★ 로딩 대기 (프록시 고려 10초)
                time.sleep(10)
                
                # 스크롤 (광고 로딩 유도)
                d.swipe(500, 1500, 500, 500, 0.3) 
                time.sleep(2)
                
                # 화면 분석 (에러 방지 처리 추가)
                is_ad = "X"
                ad_text = "-"
                
                try:
                    xml = d.dump_hierarchy() # 여기서 에러나면 무시하고 다음으로 넘어감
                    
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
                    print(f"⚠️ 화면 읽기 실패(넘어감): {xml_e}")
                
                # 시트 저장
                result_data = {
                    "날짜": datetime.now().strftime('%Y-%m-%d'),
                    "시간": datetime.now().strftime('%H:%M:%S'),
                    "키워드": keyword,
                    "회차": i,
                    "광고여부": is_ad, 
                    "비고": f"{ad_text}"
                }
                append_to_sheet(ws, result_data)
                
                # 다음 검색을 위해 검색창 비우기 (뒤로가기 대신 X버튼 누르거나 전체선택 삭제)
                # 검색창이 활성화된 상태면 X버튼이 있음
                if d(description="Clear search query").exists:
                    d(description="Clear search query").click()
                elif d(resourceId="com.google.android.youtube:id/search_clear").exists:
                    d(resourceId="com.google.android.youtube:id/search_clear").click()
                else:
                    # 없으면 돋보기 다시 눌러서 검색창 진입
                    d.click(0.9, 0.05)
                    time.sleep(1)
                    d.clear_text() # 텍스트 지우기

    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    run_android_monitoring()
