import time
import random
import pandas as pd
from urllib.parse import urlparse, parse_qs, unquote
from playwright.sync_api import sync_playwright

# ==========================================
# [설정 1] 모니터링 타겟
# ==========================================
MONITORING_TARGETS = [
    {"keyword": "토익", "target_url": "https://www.hackers.co.kr"},
    {"keyword": "공인중개사시험", "target_url": "https://land.hackers.com"},
    {"keyword": "공무원시험", "target_url": "https://gosi.hackers.com"},
    {"keyword": "경찰공무원시험", "target_url": "https://police.hackers.com"}
]

TARGET_COLLECT_COUNT = 50  # 수집할 기사 링크 개수
TARGET_AD_FOUND_LIMIT = 10 # [신규] 광고 발견 10개 채우면 1차 검사 중단
MAX_CHECK_LIMIT = 50       # 최대 검사 한도

# ==========================================
# [설정 2] 광고 매체 코드
# ==========================================
NETWORK_MAPPING = {
    "googleads": "G", "doubleclick": "G", "googlesyndication": "G",
    "criteo": "C",
    "widerplanet": "M", "mobon": "M",
    "daum": "K", "kakao": "K",
    "tg360": "T", "targetinggates": "T",
    "acetrader": "A", "acecounter": "A"
}
DISPLAY_NETWORKS = ["G", "C", "K", "M", "T", "A"]

# ==========================================
# [설정 3] 경쟁사 목록
# ==========================================
COMPETITORS = {
    "해커스": ["hackers", "champstudy"],
    "에듀윌": ["eduwill"],
    "YBM": ["ybm"],
    "파고다": ["pagoda"],
    "영단기": ["dangi"],
    "공단기": ["gong.dangi"],
    "박문각": ["pmg", "bakmun"],
    "메가": ["megaland", "mega.co.kr"],
    "야나두": ["yanadoo"],
    "시원스쿨": ["siwon"]
}
DISPLAY_COMPANIES = list(COMPETITORS.keys())

def get_clean_url(naver_redirect_url):
    if "search.naver.com/p/crd" in naver_redirect_url:
        try:
            parsed = urlparse(naver_redirect_url)
            query = parse_qs(parsed.query)
            if 'u' in query: return unquote(query['u'][0])
        except: pass
    return naver_redirect_url

def remove_mobon_icover(page):
    """모비온 아이커버(전면광고) 삭제"""
    try:
        close_selectors = [
            "#mobon_icover .btn_close", 
            "#mobon_icover button",
            "div[id*='mobon'] .close",
            ".mobon_cover .btn_close"
        ]
        
        for selector in close_selectors:
            if page.locator(selector).is_visible():
                # print("  🛡️ 모비온 닫기 클릭")
                page.locator(selector).click(force=True)
                time.sleep(0.5)
                return

        page.evaluate("""() => {
            const elements = document.querySelectorAll("div, iframe");
            elements.forEach(el => {
                if (el.id.includes('mobon') || el.className.includes('mobon')) {
                    if (el.style.display !== 'none') {
                        el.remove();
                    }
                }
            });
        }""")
    except:
        pass

def analyze_ads_count(page):
    """광고 개수 및 발견된 경쟁사 분석"""
    counts = {comp: {net: 0 for net in DISPLAY_NETWORKS} for comp in COMPETITORS}
    
    remove_mobon_icover(page)
    
    for frame in page.frames:
        try:
            frame_url = frame.url.lower()
            try: frame_content = frame.content().lower()
            except: frame_content = ""

            detected_net_code = None
            detected_company = None

            for keyword, code in NETWORK_MAPPING.items():
                if keyword in frame_url:
                    detected_net_code = code
                    break
            
            if detected_net_code and detected_net_code in DISPLAY_NETWORKS:
                for comp_name, keywords in COMPETITORS.items():
                    if any(k in frame_url for k in keywords) or any(k in frame_content for k in keywords):
                        detected_company = comp_name
                        break
                
                if detected_company:
                    counts[detected_company][detected_net_code] += 1
        except: continue
        
    return counts

def run_monitoring():
    start_time = time.time()
    total_data = {}

    with sync_playwright() as p:
        print("🚀 [최종] 모니터링 시작 (화면표시 ON / 10개 발견 시 조기 종료)")
        
        # 화면에 보이도록 설정 (0,0)
        browser = p.chromium.launch(
            channel="msedge", headless=False,
            args=["--window-position=0,0", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()

        for item in MONITORING_TARGETS:
            keyword = item["keyword"]
            target_url = item["target_url"]
            context.clear_cookies()
            
            print(f"\n==================================================")
            print(f"🔎 키워드: '{keyword}' 작업 시작")
            print(f"==================================================")
            
            # -------------------------------------------------
            # 1. 링크 수집 (스크롤 적용)
            # -------------------------------------------------
            search_url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sm=tab_opt&sort=0&photo=0&field=0&pd=0&ds=&de=&docid=&related=0&mynews=0&office_type=0&office_section_code=0&news_office_checked=&nso=so%3Ar%2Cp%3Aall&is_sug_officeid=0"
            page.goto(search_url, wait_until="domcontentloaded")
            
            collected_articles = []
            page_num = 1
            
            while len(collected_articles) < TARGET_COLLECT_COUNT:
                try:
                    # 스크롤 최하단 이동
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1.5)
                    page.keyboard.press("End")
                    time.sleep(1)

                    try: page.wait_for_selector('[data-heatmap-target=".tit"]', timeout=3000)
                    except: page.wait_for_selector(".news_tit", timeout=3000)

                    new_links = page.evaluate("""() => {
                        let nodes = document.querySelectorAll('[data-heatmap-target=".tit"]');
                        if (nodes.length === 0) nodes = document.querySelectorAll('.news_tit');
                        return Array.from(nodes).map(a => ({text: a.innerText, url: a.href}));
                    }""")
                    
                    prev_len = len(collected_articles)
                    for link in new_links:
                        if not any(saved['url'] == link['url'] for saved in collected_articles):
                            collected_articles.append(link)
                    
                    print(f"  > {page_num}페이지 수집 중... (누적 {len(collected_articles)}/{TARGET_COLLECT_COUNT}개)")
                    
                    if len(collected_articles) >= TARGET_COLLECT_COUNT:
                        break
                    
                    # 더 이상 기사가 없으면 종료
                    if len(collected_articles) == prev_len and page_num > 1:
                         # 마지막 확인 사살
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(2)
                        next_btn_check = page.locator(".btn_next")
                        if next_btn_check.count() == 0 or next_btn_check.get_attribute("aria-disabled") == "true":
                            print("  > 더 이상 기사가 없습니다.")
                            break

                    next_btn = page.locator(".btn_next")
                    if next_btn.count() > 0 and next_btn.get_attribute("aria-disabled") != "true":
                        remove_mobon_icover(page) 
                        page.evaluate("document.querySelector('.btn_next').click()")
                        page_num += 1
                        time.sleep(2.5)
                    else:
                        break
                except Exception as e:
                    print(f"  ⚠️ 수집 에러: {e}")
                    break

            collected_articles = collected_articles[:TARGET_COLLECT_COUNT]
            print(f"  > 링크 수집 완료. 1차 분석 시작 (목표: 광고 발견 {TARGET_AD_FOUND_LIMIT}건)")

            # -------------------------------------------------
            # 2. [1차] 방문 전 검사 (10개 찾으면 STOP)
            # -------------------------------------------------
            target_articles = [] # 실제 광고가 발견된 URL 리스트
            found_ad_count = 0   # 찾은 광고 개수 카운터

            for i, article in enumerate(collected_articles):
                # 10개 찾았으면 루프 탈출
                if found_ad_count >= TARGET_AD_FOUND_LIMIT:
                    print(f"  🛑 목표 광고 {TARGET_AD_FOUND_LIMIT}개를 모두 찾았습니다. 1차 검사 종료.")
                    break
                
                real_url = get_clean_url(article['url'])
                if not real_url.startswith("http"): continue
                
                if real_url not in total_data:
                    total_data[real_url] = {
                        'info': {'키워드': keyword, '기사제목': article['text']},
                        'before': {}, 'after': {}
                    }

                print(f"  > [방문전] {i+1}번째 기사 확인 중...", end="")
                try:
                    page.goto(real_url, timeout=15000, wait_until="domcontentloaded")
                    remove_mobon_icover(page)
                    
                    # 광고 로딩 유도 (스크롤)
                    page.keyboard.press("End")
                    time.sleep(2.5)
                    for _ in range(2): 
                        page.mouse.wheel(0, -1000)
                        time.sleep(0.2)
                        remove_mobon_icover(page) 
                    
                    counts = analyze_ads_count(page)
                    total_data[real_url]['before'] = counts
                    
                    # 발견된 회사 찾기
                    found_companies = []
                    for comp, nets in counts.items():
                        if sum(nets.values()) > 0:
                            found_companies.append(comp)
                    
                    if found_companies:
                        print(f" ✅ 광고발견 ({', '.join(found_companies)})")
                        target_articles.append(real_url)
                        found_ad_count += 1
                    else:
                        print(f" (타사 없음)")
                        
                except: print(" ⚠️ 에러/패스")
                time.sleep(0.5)

            if not target_articles:
                print("  ⚠️ 발견된 타사 광고가 없어 2차 검사를 생략합니다.")
                continue

            # -------------------------------------------------
            # 3. 타사 사이트 방문 (쿠키 생성)
            # -------------------------------------------------
            print(f"  > [쿠키 작업] 경쟁사 타겟 사이트 방문: {target_url}")
            try:
                page.goto(target_url)
                time.sleep(4)
                page.mouse.wheel(0, 1000)
                time.sleep(1)
            except: pass

            # -------------------------------------------------
            # 4. [2차] 방문 후 검사 (찾았던 10개만 다시 확인)
            # -------------------------------------------------
            print(f"  > [방문후] 발견했던 {len(target_articles)}개 기사 재확인 시작...")
            for url in target_articles:
                print(f"  > 재진입: {url[:40]}...", end="")
                try:
                    page.goto(url, timeout=15000, wait_until="domcontentloaded")
                    remove_mobon_icover(page)
                    
                    page.keyboard.press("End")
                    time.sleep(2.5)
                    for _ in range(2): 
                        page.mouse.wheel(0, -1000)
                        remove_mobon_icover(page)
                    
                    counts = analyze_ads_count(page)
                    total_data[url]['after'] = counts
                    
                    # 재진입 시 발견된 회사
                    found_companies = [comp for comp, nets in counts.items() if sum(nets.values()) > 0]
                    if found_companies:
                        print(f" ✅ ({', '.join(found_companies)})")
                    else:
                        print(" (사라짐/타사없음)")
                        
                except: print(" ⚠️ 실패")
                time.sleep(0.5)

        browser.close()

    # 엑셀 저장
    print("\n📊 엑셀 파일 생성 중...")
    columns = [('기본정보', '기본정보', '키워드'), ('기본정보', '기본정보', '기사제목'), ('기본정보', '기본정보', 'URL')]
    
    for comp in DISPLAY_COMPANIES:
        for phase in ['쿠키값 삭제', '방문 후']:
            for net in DISPLAY_NETWORKS:
                columns.append((comp, phase, net))
    
    multi_columns = pd.MultiIndex.from_tuples(columns, names=['회사', '시기', '매체'])
    
    rows = []
    # 데이터가 있는 것만 저장 (Pre-visit에서 10개만 돌렸으면 10개만 저장됨)
    for url, data in total_data.items():
        # 수집은 했으나 방문하지 않아 데이터가 비어있는 경우 제외
        if not data['before'] and not data['after']:
            continue
            
        row_data = [data['info']['키워드'], data['info']['기사제목'], url]
        
        for comp in DISPLAY_COMPANIES:
            # 방문 전
            before = data['before'].get(comp, {n:0 for n in DISPLAY_NETWORKS})
            for net in DISPLAY_NETWORKS:
                cnt = before.get(net, 0)
                row_data.append(cnt if cnt > 0 else "")
            
            # 방문 후
            after = data['after'].get(comp, {n:0 for n in DISPLAY_NETWORKS})
            for net in DISPLAY_NETWORKS:
                cnt = after.get(net, 0)
                row_data.append(cnt if cnt > 0 else "")
                
        rows.append(row_data)

    df = pd.DataFrame(rows, columns=multi_columns)
    file_name = f"배너모니터링_최종완료_{time.strftime('%H%M%S')}.xlsx"
    df.to_excel(file_name)
    
    end_time = time.time()
    elapsed = end_time - start_time
    print(f"\n🎉 [완료] 파일 저장됨: {file_name}")
    print(f"⏱️ 소요 시간: {int(elapsed//60)}분 {int(elapsed%60)}초")

if __name__ == "__main__":
    run_monitoring()
