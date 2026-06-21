import os
import json

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)


def generate_brand_profile(scraped_data):

    prompt = f"""
You are an expert marketing analyst.

Analyze the following website data.

Website Data:
{scraped_data}

Return ONLY valid JSON.

Format:

{{
    "brand_name": "",
    "category": "",
    "target_audience": [],
    "tone": "",
    "keywords": [],
    "brand_summary": ""
}}
"""

    response = client.chat.completions.create(
        model="deepseek/deepseek-chat-v3-0324",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2
    )

    result = response.choices[0].message.content

    result = result.replace("```json", "")
    result = result.replace("```", "")
    result = result.strip()

    return json.loads(result)