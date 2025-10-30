import os
import json
import pprint
from datetime import datetime, timedelta
from typing import TypedDict, List, Dict, Any, Optional, Annotated, Type, Literal
import operator

# OpenAI & LangChain
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser

# LangChain Community Tools & Loaders
# (17줄의 'tavily_search'는 18줄의 'tools'에 포함되므로 삭제)
from langchain_community.tools import ArxivQueryRun, TavilySearchResults 
from langchain_community.document_loaders import ArxivLoader
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

# LangGraph
from langgraph.graph import StateGraph, END

# Google & IPython (노트북/코랩용)
from googleapiclient.discovery import build
from IPython.display import display, Markdown

# Local Tools & Prompts
from tools import analyze_video_content, search_naver_news, search_global_news, search_arxiv_papers, tavily_web_search, find_videos_with_transcripts, analyze_youtube_topic
from prompts import INTENT_CLASSIFIER_PROMPT, USER_PROFILING_PROMPT, DOMESTIC_JOB_ANALYSIS_PROMPT, GLOBAL_TREND_ANALYSIS_PROMPT, GAP_ANALYSIS_PROMPTS, LLM_ROUTER_PROMPT, RECOMMEND_LEARNING, RECOMMEND_STORYTELLING_PROMPT, FINAL_REPORT_PROMPT

os.environ['OPENAI_API_KEY'] = os.environ.get('ssu')
os.environ['TAVILY_API_KEY'] = os.environ.get('tavily')
os.environ['NAVER_CLIENT_ID'] = os.environ.get('naver_client_id')
os.environ['NAVER_CLIENT_SECRET'] = os.environ.get('naver_client_secret')
os.environ['NEWS_API_KEY'] = os.environ.get('news_api_key')

def display_section(log: Dict[str, Any], key: str, title: str):
    """
    터미널에 결과를 출력하는 헬퍼 함수
    """
    message = log.get(key)
    if message and str(message).strip():
        print(f"\n{title}")
        print(message)

if __name__ == '__main__':
    # --- 1. 준비 단계 ---
    try:
        api_keys = AgentAPIs()
        youtube_service = build('youtube', 'v3', developerKey=api_keys.youtube_api_key)
        print("✅ API 및 서비스 객체 생성 완료.")
    except Exception as e:
        print(f"🔴 API 키 또는 서비스 객체 생성 실패: {e}")
        exit()

    llm_final_analyzer = ChatOpenAI(
        model="gpt-4o", # <-- 모델 이름 변경
        temperature=0.2, # 약간의 유연성을 위해 0으로 두지 않을 수 있음
        model_kwargs={"response_format": {"type": "json_object"}}
    )

    # 2. 일반적인 구조화 데이터 분석용 (대학원생급)
    llm_structured_analyzer = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}}
    )

    # 3. 창의적인 문장 생성용
    llm_creative = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=1
    )

    # 4. 빠르고 저렴한 단순 분류/변환용
    llm_fast_classifier = ChatOpenAI(
        model="gpt-3.5-turbo",
        temperature=0,
        max_tokens=100
    )

    tavily_tool = TavilySearchResults(max_results=3)
    arxiv_tool = ArxivQueryRun()

    # --- 2. LangGraph 워크플로우 생성 및 구성 ---
    workflow = StateGraph(AgentState)

    # --- 2a. 모든 노드 정의 ---
    workflow.add_node("intent_classifier", intent_classifier_node)
    workflow.add_node("user_profiling", user_profiling_node)
    # 국내 분석 (병렬)
    workflow.add_node("analyze_postings", analyze_postings_node)
    workflow.add_node("analyze_reviews", analyze_reviews_node)
    workflow.add_node("analyze_interviews", analyze_interviews_node)
    workflow.add_node("combine_domestic", combine_domestic_analysis_node)
    # 글로벌 트렌드 분석 (병렬)
    workflow.add_node("analyze_tech_trends", analyze_tech_trends_node)
    workflow.add_node("analyze_market_trends", analyze_market_trends_node)
    workflow.add_node("analyze_leaders_vision", analyze_leaders_vision_node)
    workflow.add_node("combine_global", combine_global_trends_node)
    # 갭 분석 및 라우터
    workflow.add_node("gap_analysis", gap_analysis_node)
    workflow.add_node("router", llm_router_node)
    # 최종 추천 노드
    workflow.add_node("recommend_learning", recommend_learning_node)
    workflow.add_node("recommend_storytelling", recommend_storytelling_node) # <-- 스토리텔링 노드 추가


    # --- 2b. 엣지(연결선) 정의 ---
    workflow.set_entry_point("intent_classifier")

    # 의도 분류 결과에 따라 분기
    workflow.add_conditional_edges(
        "intent_classifier",
        lambda state: state["intent_classification"],
        {
            "portfolio_analysis": "user_profiling",
            "irrelevant": END
        }
    )

    # 국내 분석 파이프라인 (병렬)
    workflow.add_edge("user_profiling", "analyze_postings")
    workflow.add_edge("user_profiling", "analyze_reviews")
    workflow.add_edge("user_profiling", "analyze_interviews")
    workflow.add_edge("analyze_postings", "combine_domestic")
    workflow.add_edge("analyze_reviews", "combine_domestic")
    workflow.add_edge("analyze_interviews", "combine_domestic")

    # 글로벌 트렌드 분석 파이프라인 (병렬)
    workflow.add_edge("combine_domestic", "analyze_tech_trends")
    workflow.add_edge("combine_domestic", "analyze_market_trends")
    workflow.add_edge("combine_domestic", "analyze_leaders_vision")
    workflow.add_edge("analyze_tech_trends", "combine_global")
    workflow.add_edge("analyze_market_trends", "combine_global")
    workflow.add_edge("analyze_leaders_vision", "combine_global")

    # 갭 분석 및 라우터 연결
    workflow.add_edge("combine_global", "gap_analysis")
    workflow.add_edge("gap_analysis", "router")

    # 라우터의 결정에 따라 추천 노드로 분기
    workflow.add_conditional_edges(
        "router",
        lambda state: state["next_action"],
        {
            "recommend_learning": "recommend_learning",
            "recommend_storytelling": "recommend_storytelling" # <-- 스토리텔링 노드로 연결
        }
    )

    # 각 추천 노드가 실행된 후 그래프 종료
    workflow.add_edge("recommend_learning", END)
    workflow.add_edge("recommend_storytelling", END) # <-- 스토리텔링 노드도 종료로 연결

    app = workflow.compile()
    print("✅ Workflow compiled successfully!")

    # --- 3. 테스트를 위한 초기 데이터 정의 ---


    user_input = {
        "목표 직무": "AI 모델 최적화 엔지니어 또는 경량화 연구원",
        "희망 기업": ["삼성전자", "SKT", "Lunit"],
        "학년/학기": "석사 졸업 후 취업준비생",
        "전공 및 복수(부)전공": "전자공학과 석사 졸업",
        "보유 기술 및 자격증": "Python, C++, Linux, PyTorch, TensorFlow, ONNX, 모델 경량화 (Pruning, Quantization), CUDA 프로그래밍 기본",
        "관련 경험 및 스펙" : "석사 졸업 논문: 'Transformer 기반 언어 모델의 Knowledge Distillation을 통한 경량화 연구', 자율주행 관련 학회에서 논문 포스터 발표 경험",
        "고민 또는 궁금한 점": "제 석사 연구 경험이 실제 산업 현장에서 어떻게 어필될 수 있을지, 면접에서 어떻게 설명해야 다른 지원자들과 차별화될 수 있을지 궁금합니다."
    }

    initial_state = {
        "user_profile_raw": user_input,
        "api_keys": api_keys,
        "youtube_service": youtube_service,
        "llm_final_analyzer": llm_final_analyzer,
        "llm_structured_analyzer": llm_structured_analyzer,
        "llm_creative": llm_creative,
        "llm_fast_classifier": llm_fast_classifier,
        "tools": {"tavily": tavily_tool, "arxiv": arxiv_tool}
    }

    # --- 4. 그래프 실행 ---
    print("\n전체 에이전트 실행 시작")
    print("="*80)
    
    execution_log = {}
    final_state = None  # <-- [추가] 최종 상태를 저장할 변수
    
    # stream을 통해 각 노드의 실행 결과를 실시간으로 확인하고 로그에 기록
    for state_update in app.stream(initial_state):
        node_name = list(state_update.keys())[0]
        node_output = state_update[node_name]
    
        # 개발자 확인용 내부 로그 출력
        print(f"\n--- [노드: {node_name}] 실행 완료 (내부 데이터) ---")
        pprint.pprint(node_output)
    
        # 실행 로그에 현재 노드의 모든 출력값을 업데이트
        if node_output:
            execution_log.update(node_output)
    
        final_state = state_update # <-- [추가] 매번 마지막 상태를 덮어쓰기
    
    print("\n\n✅ 전체 에이전트 실행 완료! 결과가 execution_log와 final_state에 저장되었습니다.")

    print("="*80)
    print(" 포트폴리오 분석 에이전트 최종 보고서 ")
    print("="*80)
    
    # 헬퍼 함수를 사용하여 각 분석 단계별 요약 메시지를 순서대로 출력합니다.
    # (Markdown '###' 제거)
    display_section(execution_log, "streaming_intent", " 분석 시작")
    display_section(execution_log, "streaming_user_profile", " 프로필 요약")
    display_section(execution_log, "streaming_domestic_analysis", "🇰🇷 국내 채용 시장 동향")
    display_section(execution_log, "streaming_global_analysis", " 글로벌 기술 트렌드")
    display_section(execution_log, "streaming_gap_analysis", " 종합 역량 진단")
    display_section(execution_log, "streaming_route", " 추천 방향 설정")
    
    # 최종 추천 보고서는 '학습' 또는 '스토리텔링' 중 하나만 존재하므로,
    # 둘 중 내용이 있는 하나를 찾아서 해당하는 제목과 함께 출력합니다.
    if execution_log.get("streaming_study_recommend"):
        display_section(execution_log, "streaming_study_recommend", "📚 맞춤형 학습 로드맵")
    elif execution_log.get("streaming_story_recommend"):
        display_section(execution_log, "streaming_story_recommend", "🎙️ 맞춤형 스토리텔링 가이드")
    
    print("="*80)
