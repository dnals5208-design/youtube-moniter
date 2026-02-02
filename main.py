import time
import uiautomator2 as u2
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import sys
import re

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
        header = ["날짜", "시간", "키워드", "회차", "광고여부", "비고"]
        
        try:
            worksheet = sh.worksheet(sheet_name)
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
# [기능] 네트워크 강제 복구 (핵심)
# ==========================================
def fix_network_settings(d):
    print("🚑 네트워크 설정 강제 수정 중...")
    
    # 1. '인터넷 연결 확인' 기능 끄기 (Captive Portal Detection Disable)
    # 이게 켜져 있으면 프록시를 감지하고 "인터넷 없음"을 띄움
    d.shell("settings put global captive_portal_mode 0")
    
    # 2. 프라이빗 DNS 끄기 (Google DNS 강제 사용 방해 금지)
    d.shell("settings put global private_dns_mode off")
    
    # 3. 비행기 모드 껐다 켜서 네트워크 재부팅
    print("   -> 네트워크 재부팅 (Airplane Mode Toggle)...")
    d.shell("cmd connectivity airplane-mode enable")
    time.sleep(2)
    d.shell("cmd connectivity airplane-mode disable")
    time.sleep(5)
    
    print("   ✅ 네트워크 패치 완료")

# ==========================================
# [기능] 인터넷 연결 확인 (엄격한 버전)
# ==========================================
def check_internet_via_browser(d):
    print("🌐 인터넷 연결 확인 중 (엄격 모드)...")
    
    # 네트워크 패치 먼저 적용
    fix_network_settings(d)
    
    d.app_start("com.android.chrome")
    time.sleep(3)
    # 구글 대신 ipinfo.io 접속 (확실한 외부 사이트)
    d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io"')
    time.sleep(10) 
    
    xml = d.dump_hierarchy()
    
    # 'No internet', 'ERR_' 문구가 있으면 실패로 간주
    if 'No internet' in xml or 'ERR_' in xml or 'DNS_' in xml:
         print("   ❌ 인터넷 연결 실패 (크롬 에러 화면)")
         return False
    
    # 접속 성공 시 보이는 키워드 (IP, Organization, Region 등)
    # 또는 구글 검색창이 아닌 실제 웹페이지 요소 확인
    print("   ✅ 인터넷 연결 성공 (에러 메시지 없음)")
    return True

# ==========================================
# [기능] 유튜브 제어
# ==========================================
def handle_popups_and_incognito(d):
    print("   🔨 초기 설정 진행 중...")
    
    for _ in range(3):
        if d(text="Don't allow").exists: d(text="Don't allow").click()
        if d(text="허용 안함").exists: d(text="허용 안함").click()
        if d(text="Got it").exists: d(text="Got it").click()
        time.sleep(1)

    print("   🕵️ 시크릿 모드 진입...")
    d.click(0.92, 0.05) 
    time.sleep(2)
    
    if d(text="Turn on Incognito").exists:
        d(text="Turn on Incognito").click()
    elif d(text="시크릿 모드 사용").exists:
        d(text="시크릿 모드 사용").click()
    elif d(resourceId="com.google.android.youtube:id/incognito_item").exists:
        d(resourceId="com.google.android.youtube:id/incognito_item").click()
    else:
        d.click(0.92, 0.05)
        time.sleep(1)
        if d(resourceId="com.google.android.youtube:id/incognito_item").exists:
             d(resourceId="com.google.android.youtube:id/incognito_item").click()
    
    time.sleep(4)
    if d(text="Got it").exists: d(text="Got it").click()
    print("   ✅ 설정 완료")

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 에뮬레이터 연결 (Android 13)...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        # 1. 인터넷 체크 및 네트워크 복구
        check_internet_via_browser(d)
        
        # 2. 유튜브 실행
        print("   -> 🔴 YouTube APP 실행")
        d.app_stop("com.google.android.youtube")
        d.app_start("com.google.android.youtube")
        time.sleep(10) 
        
        handle_popups_and_incognito(d)

        for keyword in KEYWORDS:
            print(f"\n🔎 [{keyword}] 검색 시작")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush()
                print(f"   [{i}/{REPEAT_COUNT}] 진행 중...", end=" ")
                
                # 검색창 진입
                if not d(resourceId="com.google.android.youtube:id/search_edit_text").exists:
                    d.click(0.9, 0.05) 
                    time.sleep(2)
                
                d.send_keys(keyword)
                d.press("enter")
                
                # 로딩 대기
                time.sleep(10)
                d.swipe(500, 1500, 500, 500, 0.3) 
                time.sleep(2)
                
                # 화면 분석
                is_ad = "X"
                ad_text = "-"
                
                try:
                    xml = d.dump_hierarchy()
                    texts_found = re.findall(r'(?:text|content-desc)="([^"]*)"', xml)
                    
                    # 인터넷 끊김 재확인 (상단바에 No internet이 떠있는지 체크)
                    if "No internet" in str(texts_found) or "Connect to the internet" in str(texts_found):
                        print("   ⚠️ 유튜브: 오프라인 상태 감지됨!")
                        fix_network_settings(d) # 네트워크 긴급 복구 시도
                    
                    ad_badge_found = False
                    for t in texts_found:
                        if t in ["광고", "Ad", "Sponsored", "이 광고", "앱 설치"]:
                            ad_badge_found = True
                            break
                    
                    if ad_badge_found:
                        is_ad = "O"
                        for t in texts_found:
                            if len(t) > 1 and "광고" not in t and "분 전" not in t and "조회수" not in t:
                                 if any(k in t for k in ["해커스", "에듀윌", "공단기", "메가", "경단기", "소방", "야나두", "시원스쿨", "YBM"]):
                                     ad_text = t
                                     break
                        if ad_text == "-": ad_text = "광고발견(상세미상)"
                        print(f"🚨 발견! ({ad_text})")
                    else:
                        summary = ", ".join([t for t in texts_found if len(t) > 3][:5])
                        print(f"❌ 없음 (화면: {summary}...)")

                except Exception as xml_e:
                    print(f"⚠️ 화면 읽기 실패")
                
                result_data = {
                    "날짜": datetime.now().strftime('%Y-%m-%d'),
                    "시간": datetime.now().strftime('%H:%M:%S'),
                    "키워드": keyword,
                    "회차": i,
                    "광고여부": is_ad, 
                    "비고": f"{ad_text}"
                }
                append_to_sheet(ws, result_data)
                
                # 초기화
                d.press("back")
                time.sleep(1)
                d.press("back")
                time.sleep(2)
                if d(resourceId="com.google.android.youtube:id/search_edit_text").exists:
                     d.press("back")
                     time.sleep(1)

    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    run_android_monitoring()
