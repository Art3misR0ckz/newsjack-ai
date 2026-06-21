import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)


def generate_content(
    brand_profile,
    news_match
):

    prompt = f"""
Brand Profile:

{brand_profile}


Selected News:

{news_match}


Generate:

1. Instagram Caption
2. LinkedIn Post
3. Tweet/X Post

Requirements:

- Match brand tone
- Mention the news naturally
- Do not sound like an advertisement
- Be relevant to the audience
- Keep Twitter under 280 characters

Return JSON only.
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

    return response.choices[0].message.content