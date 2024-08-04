

from openai import AsyncOpenAI
from app.config import settings

sayori_key=settings.openai_api_key

client = AsyncOpenAI(
    api_key=sayori_key
)

instruction = "Ти асистент в менеджері і твоє ім'я saory далі буде повідомлення від користувача:  "
instruction_2 = " Твоя відповідь не повинна перевищувати 600 символів."
async def ask_to_gpt(ask_to_chat: str) -> str:
    try:
        chat_completion = await client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": instruction + ask_to_chat + instruction_2,
                }
            ],
            model="gpt-4o-mini",
            temperature=1,
            max_tokens=256,
            top_p=1,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            n=2
        )
        response_1 = chat_completion.choices[0].model_dump()
        response_1 = response_1["message"]["content"]
        response_2 = chat_completion.choices[1].model_dump()
        response_2 = response_2["message"]["content"]
    
        response = [response_1, response_2]
        return response
    
    except Exception as e:
        return "Sorry, I couldn't process your request."
