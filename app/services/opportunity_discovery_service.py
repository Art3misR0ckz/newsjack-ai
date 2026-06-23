import json

from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)


def discover_opportunities(raw_topics):

    prompt = f"""
You are an expert marketing strategist.

Below is a list of trending topics from Google Trends and News.

Your job:

1. Remove random people names.
2. Remove local searches.
3. Remove weather searches.
4. Remove irrelevant topics.
5. Keep only topics that brands can realistically use for campaigns.

Examples of GOOD opportunities:

- FIFA Club World Cup
- International Yoga Day
- Monsoon Season
- AI Product Launches
- Apple Product Launches
- House of the Dragon
- Sustainability Trends

Return ONLY valid JSON.

Format:

[
    {{
        "topic":"...",
        "reason":"..."
    }}
]

Topics:

{raw_topics}
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b:free",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    result = response.choices[0].message.content

    print("\nGPT RESPONSE:\n")
    print(result)

    result = result.replace("```json", "")
    result = result.replace("```", "")
    result = result.strip()

    return json.loads(result)