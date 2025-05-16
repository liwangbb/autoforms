import logging

from openai import AzureOpenAI

from services.config.openai_config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_GPT4_DEPLOYMENT,
)

logger = logging.getLogger(__name__)

SUPPORTED_OPENAI_EXCEPTIONS = (
    ImportError,
    ConnectionError,
    TimeoutError,
    ValueError,
    KeyError,
    AttributeError,
    TypeError,
)


def get_azure_openai_client_and_deployment():
    """
    Returns:
        tuple: (AzureOpenAI client, deployment name)
    """
    client = AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_version=AZURE_OPENAI_API_VERSION,
    )
    return client, AZURE_OPENAI_GPT4_DEPLOYMENT


def chat_with_azure_openai(
    client, deployment, messages, temperature=0.5, max_tokens=2000
):
    """
    Sends a chat completion request to Azure OpenAI.

    Args:
        client: AzureOpenAI client.
        deployment: The deployment name (model).
        messages: List of message dicts.
        temperature: Sampling temperature.
        max_tokens: Max number of tokens to generate.

    Returns:
        The response object from Azure OpenAI.
    """
    try:
        return client.chat.completions.create(
            model=deployment,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as e:
        raise RuntimeError(f"Chat completion failed: {e}") from e


def handle_openai_exceptions(e):
    if isinstance(e, ImportError):
        logger.error("OpenAI module import error: %s", str(e))
    elif isinstance(e, ConnectionError):
        logger.error("Connection error with OpenAI API: %s", str(e))
    elif isinstance(e, TimeoutError):
        logger.error("Timeout error with OpenAI API: %s", str(e))
    elif isinstance(e, ValueError):
        logger.error("Invalid parameter to OpenAI API: %s", str(e))
    elif isinstance(e, KeyError):
        logger.error("Missing key in OpenAI response: %s", str(e))
    elif isinstance(e, (AttributeError, TypeError)):
        logger.error("Error parsing OpenAI response: %s", str(e))
    else:
        logger.error("Unexpected error during OpenAI call: %s", str(e))
