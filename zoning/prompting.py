import json

import diskcache as dc
import openai
import rich
from tenacity import retry, retry_if_exception_type, wait_random_exponential

from .utils import cached, get_project_root, limit_global_concurrency

cache = dc.Cache(get_project_root() / ".diskcache")


@cached(cache, lambda *args, **kwargs: json.dumps(args) + json.dumps(kwargs))
@retry(
    retry=retry_if_exception_type(
        (
            openai.error.APIError,
            openai.error.RateLimitError,
            openai.error.APIConnectionError,
            openai.error.ServiceUnavailableError,
            openai.error.Timeout,
            openai.error.TryAgain,
        )
    ),
    wait=wait_random_exponential(multiplier=1, max=60),
)
@limit_global_concurrency(100)
async def prompt(
    model_name: str,
    input_prompt: str | list[dict[str, str]],
    max_tokens=256,
    formatted_response=False,
) -> str | None:
    base_params = {
        "model": model_name,
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }

    try:
        match model_name:
            case "text-davinci-003":
                resp = await openai.Completion.acreate(
                    **base_params,
                    prompt=input_prompt,
                )
                top_choice = resp.choices[0]  # type: ignore
                return top_choice.text
            case "gpt-3.5-turbo" | "gpt-4":
                resp = await openai.ChatCompletion.acreate(
                    **base_params,
                    messages=input_prompt,
                )
                top_choice = resp.choices[0]  # type: ignore
                return top_choice.message.content
            case "gpt-4-1106-preview":
                if not formatted_response:
                    resp = await openai.ChatCompletion.acreate(
                        **base_params,
                        messages=input_prompt,
                    )
                    top_choice = resp.choices[0]  # type: ignore
                    return top_choice.message.content
                else:
                    resp = await openai.ChatCompletion.acreate(
                        **base_params,
                        messages=input_prompt,
                        response_format={"type": "json_object"}
                    )
                    top_choice = resp.choices[0]  # type: ignore
                    return top_choice.message.content
            case _:
                raise ValueError(f"Unknown model name: {model_name}")
    except openai.error.InvalidRequestError as exc:
        rich.print("Error running prompt", exc)
        return None
