import os
import datetime
import sys
import time
import re
import json
import urllib.request

# 한글 출력 깨짐 방지 (Windows 환경 대응 강화)
try:
    if sys.stdout.encoding.lower() != 'utf-8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
except Exception:
    pass

from notion_client import Client
import google.generativeai as genai
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경 변수 필수 체크
required_env_vars = ["NOTION_TOKEN", "NOTION_DATABASE_ID", "GEMINI_API_KEY"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]

if missing_vars:
    print(f"❌ 오류: 다음 환경 변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
    sys.exit(1)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# 라이브러리 설정 및 인증 (기존의 검증된 방식)
genai.configure(api_key=GEMINI_API_KEY)

notion = Client(auth=os.getenv("NOTION_TOKEN"))
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

def send_discord_webhook(status, blog_name, title=None, error=None):
# (기존 함수 유지)
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ Discord Webhook URL이 설정되지 않았습니다. 알림을 건너뜁니다.")
        return

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if status == "success":
        color = 3066993  # Green
        description = f"**{blog_name}** 저장 완료\n제목: {title}"
        footer = "✅ 자동 발행 성공"
    else:
        color = 15158332  # Red
        description = f"**{blog_name}** 최종 실패\n오류: {error}"
        footer = "❌ 자동 발행 실패"

    payload = {
        "embeds": [{
            "title": "Notion Auto Blog 알림",
            "description": description,
            "color": color,
            "footer": {"text": f"{now} | {footer}"}
        }]
    }

    print(f"📡 Discord 웹후크 전송 시도 중... (상태: {status}, 블로그: {blog_name})")
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=data,
            headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req) as response:
            if response.status in [200, 204]:
                print(f"✨ Discord 알림 전송 성공! (HTTP {response.status})")
            else:
                print(f"⚠️ Discord 알림 전송 결과 (HTTP {response.status})")
    except urllib.error.HTTPError as e:
        print(f"❌ Discord 웹후크 HTTP 오류: {e.code} {e.reason}")
        print(f"   내용: {e.read().decode('utf-8', errors='ignore')}")
    except Exception as e:
        print(f"❌ Discord 웹후크 일반 오류: {e}")

# 블로그별 설정 및 프롬프트 강화
COMMON_FORMAT = """
출력 형식:
# [제목]
키워드: [쉼표로 구분된 키워드 3-5개]
참고링크: [관련된 신뢰할 수 있는 웹사이트 URL 하나]
이미지1: [주제와 어울리는 Unsplash 이미지 URL 1]
이미지2: [주제와 어울리는 Unsplash 이미지 URL 2]
---
[여기에 본문 내용을 3,000자 이상 아주 상세하게 작성하세요. 소제목을 여러 개 사용하고 가독성 있게 작성하세요.]
"""

BLOG_TYPES = {
    "네이버(금융)": {
        "prompt": "금융 전문가로서 최근 금리 변화, 환율 변동, 주식 시장 트렌드, 또는 새로운 금융 상품 중 하나를 선정해 일반인도 이해하기 쉬우면서도 깊이 있는 심층 분석글을 작성해줘." + COMMON_FORMAT,
        "tags": "금융, 재테크, 경제"
    },
    "티스토리(행복한 세상)": {
        "prompt": f"""오늘은 {datetime.datetime.now().strftime('%Y-%m-%d')}입니다. 
        당신은 인기 블로거입니다. 다음 순서로 작업하세요:
        1. 현재 구글이나 네이버의 실시간 인기 검색어 또는 최신 생활 트렌드를 하나 선정하세요.
        2. 그 주제에 대해 독자들에게 매우 유용하고 실질적인 정보를 제공하는 가이드형 글을 작성하세요.
        3. 반드시 한국어 기준 공백 포함 3,000자 이상의 매우 방대한 분량으로 작성해야 합니다.
        4. 정보의 정확성을 위해 구체적인 데이터나 절차를 포함하세요.
        """ + COMMON_FORMAT,
        "tags": "생활정보, 트렌드, 꿀팁"
    },
    "티스토리(매일 비평)": {
        "prompt": "오늘의 주요 사회, 문화, 또는 정치 이슈 중 하나를 선정해 다각도로 분석하고 날카로운 통찰을 담은 비평글을 작성해줘. 독자들이 생각할 거리를 던져주는 깊이 있는 논조를 유지해줘." + COMMON_FORMAT,
        "tags": "뉴스분석, 시사트렌드, 사회비평"
    },
    "티스토리(직장 생활)": {
        "prompt": """당신은 15년 차 시니어 직장인이자 커리어 코치입니다. '슬기로운 직장생활'을 주제로 다음 지침에 따라 글을 작성하세요:
        1. 주제 선정: 비즈니스 에티켓, 직장 내 대인관계 노하우, 커리어 성장(IT/자기계발), 효율적인 협업 도구 사용법, 또는 상사/동료와의 소통법 중 하나를 선택하세요.
        2. 말투: '행복한 인생 광장' 블로그처럼 따뜻하면서도 전문적인 조언자의 톤을 유지하세요. (~하세요, ~입니다 체 사용)
        3. 구성: '숫자'를 활용한 리스트(예: ~을 위한 팁 5가지)를 포함하고, 서론-본론-결론의 체계적인 구조로 작성하세요.
        4. 분량: 반드시 한국어 기준 공백 포함 2,000자 이상의 상세한 분량이어야 합니다. 실질적인 사례를 많이 포함하세요.
        """ + COMMON_FORMAT,
        "tags": "직장생활, 커리어, 슬기로운회사생활, 자기계발"
    }
}

def generate_content_with_retry(blog_name, prompt, max_retries=3):
    last_error = "알 수 없는 오류"
    for attempt in range(max_retries):
        try:
            target_model_name = 'gemini-1.5-flash'
            print(f"[{blog_name}] 글 생성 중... (모델: {target_model_name}, 시도 {attempt + 1}/{max_retries})")
            
            model = genai.GenerativeModel(target_model_name)
            response = model.generate_content(prompt)
            text = response.text
            
            if not text:
                raise ValueError("API 응답에 텍스트가 없습니다.")
            
            # 파싱 로직 개선
            title_match = re.search(r'#\s*(.*)', text)
            title = title_match.group(1).strip() if title_match else "제목 없음"
            
            keywords_match = re.search(r'키워드:\s*(.*)', text)
            keywords = keywords_match.group(1).strip() if keywords_match else ""
            
            ref_link_match = re.search(r'참고링크:\s*(.*)', text)
            ref_link = ref_link_match.group(1).strip() if ref_link_match else ""
            
            # 이미지 추출
            img_urls = []
            img_urls.extend(re.findall(r'이미지\d*:\s*(https?://\S+)', text))
            if not img_urls:
                single_img = re.search(r'이미지:\s*(https?://\S+)', text)
                if single_img:
                    img_urls = [single_img.group(1).strip()]
            
            # 유효하지 않은 Unsplash URL (Hallucination) 방지 및 보정
            fixed_img_urls = []
            for url in img_urls:
                if "unsplash.com" in url:
                    # Unsplash 이미지가 깨질 경우를 대비해 랜덤 고해상도 키워드 추가
                    if "?" not in url:
                        url += "?auto=format&fit=crop&q=80&w=1080"
                    fixed_img_urls.append(url)
            
            # 본문 추출 로직 강화 (구분선 기준 최장 텍스트 선택)
            parts = text.split('---')
            if len(parts) > 1:
                # 메타데이터를 제외한 가장 긴 부분을 본문으로 간주
                content = max(parts[1:], key=len).strip()
            else:
                content = text.strip()
            
            # 본문이 너무 짧으면 (파싱 실패 가능성) 전체 텍스트에서 제목/이미지 등만 제외 시도
            if len(content) < 500:
                print(f"⚠️ 본문 추출 결과가 너무 짧습니다 ({len(content)}자). 전체 텍스트를 사용합니다.")
                content = text
            
            print(f"📝 추출된 본문 분량: {len(content)}자")
            
            return {
                "title": title,
                "keywords": keywords,
                "ref_link": ref_link,
                "img_urls": fixed_img_urls,
                "content": content
            }
            
        except Exception as e:
            last_error = str(e)
            print(f"오류 발생: {last_error}")
            if "429" in last_error or "RESOURCE_EXHAUSTED" in last_error:
                wait_time = (attempt + 1) * 60
                print(f"⏳ 할당량 부족. {wait_time}초 후 다시 시도합니다...")
                time.sleep(wait_time)
            else:
                time.sleep(5)
                
    raise Exception(f"글 생성 실패: {last_error}")

def send_to_notion(blog_name, data):
    properties = {
        "글 제목": {"title": [{"text": {"content": data["title"]}}]},
        "블로그 명": {"select": {"name": blog_name}},
        "작성일": {"date": {"start": datetime.datetime.now().isoformat()}},
        "진행사항": {"select": {"name": "대기중"}},
        "주요 키워드": {"rich_text": [{"text": {"content": data["keywords"]}}]},
    }
    
    if data["ref_link"].startswith("http"):
        properties["참고링크"] = {"url": data["ref_link"]}
    
    if data["img_urls"] and data["img_urls"][0].startswith("http"):
        properties["이미지 파일"] = {
            "files": [{"name": "MainImage", "type": "external", "external": {"url": data["img_urls"][0]}}]
        }

    content_blocks = []
    
    # 1. 이미지 블록 추가 (유효한 URL만)
    for url in data["img_urls"]:
        if url.startswith("http"):
            content_blocks.append({
                "object": "block",
                "type": "image",
                "image": {"type": "external", "external": {"url": url}}
            })

    # 2. 본문 내용 추가
    content = data["content"]
    # Notion API 제한으로 한 블록당 2000자씩 분할
    for i in range(0, len(content), 2000):
        chunk = content[i:i+2000]
        if chunk.strip():
            content_blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                }
            })

    # Notion 페이지 생성 (최대 100개 블록 제한 주의)
    notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties=properties,
        children=content_blocks[:100]
    )

def main():
    # 현재 요일 확인 (0: 월요일, 1: 화요일, ..., 6: 일요일)
    weekday = datetime.datetime.now().weekday()
    
    for blog_name, config in BLOG_TYPES.items():
        # '티스토리(직장 생활)'은 월요일과 화요일(오늘)에 실행 (추후 필요시 다시 월요일로 복구 가능)
        if blog_name == "티스토리(직장 생활)" and weekday not in [0, 1]:
            print(f"⏭️ {blog_name}은 지정된 요일에만 발행됩니다. 오늘은 건너뜁니다.")
            continue
            
        try:
            data = generate_content_with_retry(blog_name, config["prompt"])
            send_to_notion(blog_name, data)
            print(f"✅ {blog_name} 저장 완료")
            send_discord_webhook("success", blog_name, title=data["title"])
            time.sleep(10)
        except Exception as e:
            print(f"❌ {blog_name} 최종 실패: {e}")
            send_discord_webhook("error", blog_name, error=str(e))

if __name__ == '__main__':
    main()
