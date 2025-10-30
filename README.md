!pip install -q openai==1.101.0 langchain==0.3.27 langchain-core==0.3.74 langchain-openai==0.3.30 langchain-community==0.3.27 pytube==15.0.0 tavily-python==0.7.11 youtube-search-python==1.6.6 langgraph==0.6.4 arxiv==2.2.0 pymupdf==1.26.3 youtube_transcript_api==1.2.2

# Agent 기반 개인 맞춤형 취업 지원 플랫폼

(2025년 8월 완료한 프로젝트 아카이브입니다.)

LangGraph를 기반으로 사용자의 프로필을 분석하여 맞춤형 포트폴리오 개선안을 제시하는 AI 에이전트 프로젝트입니다.

---

## ⚙️ 환경 설정 (Setup)

### 1. 주요 라이브러리 (Dependencies)
본 프로젝트는 다음의 주요 라이브러리를 사용합니다. `main.py` 파일 실행 전, 이 라이브러리들이 설치되어 있어야 합니다.

* `langchain`
* `langgraph`
* `langchain-openai`
* `langchain-community`
* `pydantic`
* `google-api-python-client` (YouTube 검색용)
* `tavily-python` (Tavily 검색용)

### 2. 필수 API 키 (Required API Keys)
본 프로젝트는 다양한 외부 API를 활용합니다. `main.py`를 실행하기 전에, 다음 API 키들이 **시스템 환경 변수**로 설정되어 있어야 합니다.

* `OPENAI_API_KEY` (OpenAI)
* `TAVILY_API_KEY` (Tavily Search)
* `NAVER_CLIENT_ID` (Naver Search)
* `NAVER_CLIENT_SECRET` (Naver Search)
* `NEWS_API_KEY` (NewsAPI.org 등 글로벌 뉴스 검색용)

---

## 📁 프로젝트 구조 (Project Structure)

이 리포지토리는 다음과 같은 파일들로 구성되어 있습니다.

1.  (선택) 가상 환경을 생성하고 활성화합니다.
2.  필요한 라이브러리를 설치합니다. (`pip install -r requirements.txt` 또는 위 '주요 라이브러리' 참고)
3.  터미널(또는 시스템)에 위에서 언급된 5개의 `필수 API 키`를 환경 변수로 설정합니다.
4.  메인 스크립트를 실행합니다:
    ```bash
    python main.py
    ```
