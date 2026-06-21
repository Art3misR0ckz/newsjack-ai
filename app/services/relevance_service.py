import os
import json

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

def select_best_news(
    brand_profile,
    news_articles
):

    prompt = f"""
Brand Profile:
{brand_profile}

News Articles:
{news_articles}

Task:

Choose the SINGLE most relevant news article.

Return ONLY valid JSON.

Format:

{{
    "selected_title":"",
    "relevance_score":0,
    "angle":"",
    "reason":""
}}

Possible angles:

- informative
- inspirational
- humorous
- educational
- empathetic
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b:free",
        messages=[
            {
                "role":"user",
                "content":prompt
            }
        ]
    )

    result = response.choices[0].message.content

    result = result.replace(
        "```json",
        ""
    )

    result = result.replace(
        "```",
        ""
    )

    result = result.strip()

    return json.loads(result)
