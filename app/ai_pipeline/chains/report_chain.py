## ✅ 전체 수정된 report_chain.py

"""
요약 리포트 생성 LLM Chain
규제 변경 + 영향평가 → 경영진용 요약 리포트 생성

Author: 남지수 (BE2 - Database Engineer)
"""

from typing import Dict, Any, Optional
import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser


# 로깅 설정
logger = logging.getLogger(__name__)


class ReportGeneratorChain:
    """
    규제 변경 내용과 영향평가를 기반으로 요약 리포트를 생성하는 LLM Chain
    
    주요 기능:
    - 규제 변경 사항의 핵심 내용 추출
    - 영향도 점수 기반 우선순위 분석
    - 경영진을 위한 실행 가능한 액션 아이템 제시
    """
    
    def __init__(
        self, 
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 2000
    ):
        """
        Chain 초기화
        
        Args:
            model: 사용할 LLM 모델명
            temperature: 생성 다양성 (0~1, 낮을수록 일관적)
            max_tokens: 최대 생성 토큰 수
        """
        self.model_name = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # LLM 초기화
        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # 프롬프트 템플릿 구성
        self.prompt = self._build_prompt_template()
        
        # Chain 구성
        self.chain = self.prompt | self.llm | StrOutputParser()
        
        logger.info(f"ReportGeneratorChain 초기화 완료 - 모델: {model}")
    
    def _build_prompt_template(self) -> ChatPromptTemplate:
        """
        요약 리포트 생성용 프롬프트 템플릿 구성
        
        Returns:
            ChatPromptTemplate: LangChain 프롬프트 템플릿
        """
        return ChatPromptTemplate.from_messages([
            ("system", """당신은 글로벌 담배 규제 분석 전문가입니다.
규제 변경 내용과 제품별 영향평가 데이터를 받아서 **경영진을 위한 요약 리포트**를 작성하는 것이 임무입니다.

**작성 원칙:**
1. **간결성**: 핵심만 추려서 A4 1장 분량으로 작성
2. **명확성**: 전문 용어는 쉽게 풀어서 설명
3. **실행 가능성**: 즉시 실행 가능한 구체적 조치사항 제시
4. **우선순위**: 고위험 제품 중심으로 기술

**리포트 구조:**
1. 규제 변경 핵심 요약 (3줄 이내)
2. 영향도 분석 (고/중/저위험 제품 현황)
3. 즉시 대응이 필요한 액션 아이템 (우선순위순)
4. 예상 리스크 및 권고사항

**톤앤매너:**
- 전문적이지만 이해하기 쉽게
- 사실 기반 객관적 분석
- 긍정적이지만 위험은 명확히 전달"""),
            
            ("human", """다음 규제 변경 정보를 분석하여 요약 리포트를 작성해주세요.

# 📋 규제 변경 내용
{regulation_text}

# 📊 영향평가 결과
{impact_summary}

# 🌍 규제 메타데이터
- **국가**: {country}
- **시행일**: {effective_date}
- **규제 ID**: {regulation_id}

---

위 정보를 바탕으로 경영진용 요약 리포트를 작성해주세요.
마크다운 형식으로 작성하되, 헤더는 ##부터 시작하세요.""")
        ])
    
    async def generate(
        self,
        regulation_text: str,
        impact_scores: Dict[str, float],
        metadata: Dict[str, Any]
    ) -> str:
        """
        요약 리포트 생성 (비동기)
        
        Args:
            regulation_text: 규제 변경 내용 텍스트
            impact_scores: 제품별 영향도 점수 딕셔너리
            metadata: 메타데이터 (국가, 시행일 등)
        
        Returns:
            str: 생성된 요약 리포트 (마크다운 형식)
        
        Raises:
            Exception: LLM 호출 실패 시
        """
        logger.info(f"요약 리포트 생성 시작 - 제품 수: {len(impact_scores)}")
        
        # 입력 데이터 전처리
        impact_summary = self._format_impact_scores(impact_scores)
        
        # 프롬프트 입력 구성
        prompt_input = {
            "regulation_text": self._truncate_text(regulation_text, max_length=1500),
            "impact_summary": impact_summary,
            "country": metadata.get("country_code", "N/A"),
            "effective_date": metadata.get("effective_date", "N/A"),
            "regulation_id": metadata.get("regulation_id", "N/A")
        }
        
        try:
            # LLM Chain 실행
            report = await self.chain.ainvoke(prompt_input)
            
            logger.info(f"요약 리포트 생성 완료 - 길이: {len(report)}")
            return report
        
        except Exception as e:
            logger.error(f"LLM 호출 실패: {str(e)}")
            raise
    
    def generate_sync(
        self,
        regulation_text: str,
        impact_scores: Dict[str, float],
        metadata: Dict[str, Any]
    ) -> str:
        """
        요약 리포트 생성 (동기)
        
        Args:
            regulation_text: 규제 변경 내용 텍스트
            impact_scores: 제품별 영향도 점수 딕셔너리
            metadata: 메타데이터
        
        Returns:
            str: 생성된 요약 리포트
        """
        logger.info(f"요약 리포트 생성 시작 (동기) - 제품 수: {len(impact_scores)}")
        
        impact_summary = self._format_impact_scores(impact_scores)
        
        prompt_input = {
            "regulation_text": self._truncate_text(regulation_text, max_length=1500),
            "impact_summary": impact_summary,
            "country": metadata.get("country_code", "N/A"),
            "effective_date": metadata.get("effective_date", "N/A"),
            "regulation_id": metadata.get("regulation_id", "N/A")
        }
        
        try:
            report = self.chain.invoke(prompt_input)
            logger.info(f"요약 리포트 생성 완료 - 길이: {len(report)}")
            return report
        
        except Exception as e:
            logger.error(f"LLM 호출 실패: {str(e)}")
            raise
    
    def _format_impact_scores(self, impact_scores: Dict[str, float]) -> str:
        """영향도 점수를 LLM이 이해하기 쉬운 텍스트로 포맷팅"""
        
        high_risk = [(pid, score) for pid, score in impact_scores.items() if score >= 0.7]
        medium_risk = [(pid, score) for pid, score in impact_scores.items() if 0.3 <= score < 0.7]
        low_risk = [(pid, score) for pid, score in impact_scores.items() if score < 0.3]
        
        high_risk.sort(key=lambda x: x[1], reverse=True)
        medium_risk.sort(key=lambda x: x[1], reverse=True)
        low_risk.sort(key=lambda x: x[1], reverse=True)
        
        lines = []
        
        lines.append(f"**🔴 고위험 제품: {len(high_risk)}개**")
        if high_risk:
            for pid, score in high_risk[:5]:
                lines.append(f"  - 제품 ID {pid}: 영향도 {score:.3f}")
            if len(high_risk) > 5:
                lines.append(f"  - ... 외 {len(high_risk) - 5}개")
        else:
            lines.append("  - 해당 없음")
        
        lines.append("")
        
        lines.append(f"**🟡 중위험 제품: {len(medium_risk)}개**")
        if medium_risk:
            for pid, score in medium_risk[:3]:
                lines.append(f"  - 제품 ID {pid}: 영향도 {score:.3f}")
            if len(medium_risk) > 3:
                lines.append(f"  - ... 외 {len(medium_risk) - 3}개")
        else:
            lines.append("  - 해당 없음")
        
        lines.append("")
        lines.append(f"**🟢 저위험 제품: {len(low_risk)}개**")
        lines.append("  - 영향 미미, 모니터링 수준")
        
        return "\n".join(lines)
    
    def _truncate_text(self, text: str, max_length: int = 1500) -> str:
        """텍스트를 지정된 길이로 자르기"""
        if len(text) <= max_length:
            return text
        
        truncated = text[:max_length].rsplit(' ', 1)[0]
        return truncated + "..."
    
    def update_model(self, model: str, temperature: Optional[float] = None):
        """모델 설정 업데이트"""
        self.model_name = model
        if temperature is not None:
            self.temperature = temperature
        
        self.llm = ChatOpenAI(
            model=model,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        
        self.chain = self.prompt | self.llm | StrOutputParser()
        logger.info(f"모델 업데이트 완료 - 새 모델: {model}")


if __name__ == "__main__":
    """로컬 테스트용 코드"""
    import asyncio
    
    async def test_chain():
        chain = ReportGeneratorChain(model="gpt-4o-mini", temperature=0.3)
        
        test_regulation = """
        미국 FDA는 2026년 1월 1일부터 담배 제품의 니코틴 함량 상한선을 
        현행 1.2mg에서 0.9mg으로 강화합니다.
        """
        
        test_impact_scores = {
            "product_001": 0.92,
            "product_002": 0.85,
            "product_003": 0.45
        }
        
        test_metadata = {
            "country_code": "US",
            "effective_date": "2026-01-01",
            "regulation_id": 12345
        }
        
        print("=== LLM Chain 테스트 시작 ===\n")
        report = await chain.generate(test_regulation, test_impact_scores, test_metadata)
        print(report)
    
    asyncio.run(test_chain())