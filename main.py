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
# [기능] 구글 시트 연결 및 한 줄 쓰기
# ==========================================
def get_worksheet():
    """구글 시트 워크시트 객체를 가져옵니다."""
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
            # 헤더 추가
            header = ["날짜", "시간", "키워드", "회차", "광고여부", "비고"]
            worksheet.append_row(header)
            
        return worksheet
    except Exception as e:
        print(f"❌ 구글 시트 연결 실패: {e}")
        return None

def append_to_sheet(worksheet, data):
    """데이터 한 줄을 즉시 업로드합니다."""
    if worksheet:
        try:
            # data 딕셔너리를 리스트 순서대로 변환
            row = [
                data["날짜"],
                data["시간"],
                data["키워드"],
                data["회차"],
                data["광고여부"],
                data["비고"]
            ]
            worksheet.append_row(row)
            print("   📤 시트 업데이트 완료")
        except Exception as e:
            print(f"   ⚠️ 시트 저장 실패: {e}")

# ==========================================
# [기능] 유튜브 제어 로직
# ==========================================
def handle_popups_and_incognito(d):
    print("   🔨 초기 설정(팝업/시크릿모드) 진행 중...")
    
    # 1. 초기 팝업 닫기 (알림 등)
    if d(text="Don't allow").exists: d(text="Don't allow").click()
    if d(text="허용 안함").exists: d(text="허용 안함").click()
    time.sleep(2)

    # 2. 시크릿 모드 켜기
    print("   🕵️ 시크릿 모드 진입 시도...")
    
    # 프로필 아이콘 찾기 (우측 상단)
    # 여러 가지 방법으로 시도
    if d(description="Account").exists:
        d(description="Account").click()
    elif d(resourceId="com.google.android.youtube:id/mobile_user_account_avatar").exists:
        d(resourceId="com.google.android.youtube:id/mobile_user_account_avatar").click()
    elif d(description="계정").exists:
        d(description="계정").click()
    else:
        # 못 찾으면 좌표 클릭 (우측 상단 구석)
        d.click(0.92, 0.05)
    
    time.sleep(2)
    
    # 메뉴에서 '시크릿 모드 사용' 클릭
    if d(text="Turn on Incognito").exists:
        d(text="Turn on Incognito").click()
    elif d(text="시크릿 모드 사용").exists:
        d(text="시크릿 모드 사용").click()
    elif d(resourceId="com.google.android.youtube:id/incognito_item").exists:
        d(resourceId="com.google.android.youtube:id/incognito_item").click()
        
    time.sleep(3)
    
    # 'Got it' 팝업 닫기
    if d(text="Got it").exists: d(text="Got it").click()
    if d(text="확인").exists: d(text="확인").click()
    
    print("   ✅ 시크릿 모드 설정 완료")

def run_android_monitoring():
    # 1. 시트 연결 (시작할 때 한 번 연결)
    ws = get_worksheet()
    
    print(f"📱 [MO] 안드로이드 에뮬레이터 연결 시도...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        print(f"   -> 연결 성공! 모델: {d.info.get('model')}")
        
        # 2. 유튜브 실행
        print("   -> 🔴 YouTube APP 실행 중...")
        d.app_stop("com.google.android.youtube")
        d.app_start("com.google.android.youtube")
        time.sleep(15) # 앱 로딩 충분히 대기
        
        # 3. 시크릿 모드 전환
        handle_popups_and_incognito(d)

        # 4. IP 확인 (브라우저 잠시 다녀오기)
        # (시크릿 모드가 풀릴 수 있으므로, 앱 내 검색으로 IP 확인은 어려움. 브라우저로 체크만 하고 복귀)
        print("🌍 IP 상태 점검...")
        d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io/json"')
        time.sleep(10)
        ip_xml = d.dump_hierarchy()
        if "KR" in ip_xml or "Korea" in ip_xml:
            print("   ✅ 한국 IP 확인됨")
        else:
            print("   ⚠️ 한국 IP 로딩 실패 (터널링 속도 문제일 수 있음)")
        
        # 다시 유튜브로 복귀
        d.app_start("com.google.android.youtube")
        time.sleep(5)

        # 5. 키워드 검색 반복
        for keyword in KEYWORDS:
            print(f"\n🔎 키워드 [{keyword}] 검색 시작")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush() # 로그 즉시 출력 강제
                print(f"   [{i}/{REPEAT_COUNT}] 검색 중...", end=" ")
                
                # 돋보기 클릭
                if d(description="Search").exists:
                    d(description="Search").click()
                elif d(resourceId="com.google.android.youtube:id/menu_item_search").exists:
                    d(resourceId="com.google.android.youtube:id/menu_item_search").click()
                else:
                    d.click(0.9, 0.05) # 좌표
                
                time.sleep(2)
                
                # 검색어 입력 및 엔터
                d.send_keys(keyword)
                time.sleep(1)
                d.press("enter")
                
                # ★ 로딩 대기 및 스크롤 (가장 중요)
                time.sleep(15) 
                d.swipe(500, 1500, 500, 500, 0.5) # 아래로 쓱
                time.sleep(3)
                
                # 화면 분석
                xml = d.dump_hierarchy()
                
                is_ad = "X"
                ad_text = "-"
                
                # 앱 광고 식별
                if 'text="광고"' in xml or 'text="Ad"' in xml or 'text="Sponsored"' in xml:
                    is_ad = "O"
                    # 광고주 텍스트 추출
                    lines = [line.split('"')[0] for line in xml.split('text="') if '"' in line]
                    for line in lines:
                        if len(line) > 1 and "광고" not in line and "분 전" not in line:
                             if any(k in line for k in ["해커스", "에듀윌", "공단기", "메가", "경단기", "소방"]):
                                 ad_text = line
                                 break
                    if ad_text == "-": ad_text = "광고발견"
                    print(f"🚨 발견! ({ad_text})")
                else:
                    print(f"❌ 없음")
                
                # 결과 데이터 구성
                result_data = {
                    "날짜": datetime.now().strftime('%Y-%m-%d'),
                    "시간": datetime.now().strftime('%H:%M:%S'),
                    "키워드": keyword,
                    "회차": i,
                    "광고여부": is_ad, 
                    "비고": f"YouTube App(Secret) / {ad_text}"
                }
                
                # ★ 실시간 시트 업로드
                append_to_sheet(ws, result_data)
                
                # 초기화 (홈으로 가지 말고 검색창만 닫기 위해 뒤로가기)
                d.press("back") # 키보드 내림/검색결과 닫기
                if d(resourceId="com.google.android.youtube:id/search_edit_text").exists:
                     d.press("back") # 검색창 닫기
                time.sleep(2)

    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    run_android_monitoring()
