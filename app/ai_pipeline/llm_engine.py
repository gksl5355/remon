import os
import json
from openai import AsyncOpenAI

class LLMEngine:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            print("⚠️ OpenAI API Key가 설정되지 않았습니다.")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=self.api_key)

    async def analyze_regulation(self, text_content: str, country_code: str):
        if not self.client:
            return None
        
        # 텍스트가 너무 짧으면 분석 스킵 (오류 방지)
        if len(text_content) < 50:
            print("⚠️ 텍스트가 너무 짧아 AI 분석을 생략합니다.")
            return None

        # 비용 절약을 위해 앞부분 15,000자만 분석 (필요시 늘리세요)
        truncated_text = text_content[:15000]

        print(f"🧠 [AI Engine] GPT-4o-mini 분석 요청 중... (텍스트 길이: {len(truncated_text)}자)")

        system_prompt = """
        You are a Regulation Analyst AI. Analyze the text and output JSON.
        Format:
        {
            "summary": "Korean summary (3 sentences)",
            "impact_level": "High/Medium/Low",
            "key_keywords": ["keyword1", "keyword2"]
        }
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Country: {country_code}\nText:\n{truncated_text}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result = response.choices[0].message.content
            return json.loads(result)
            
        except Exception as e:
            print(f"❌ OpenAI 호출 중 에러 발생: {e}")
            return None