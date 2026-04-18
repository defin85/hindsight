import pytest

from hindsight_api.extensions import OperationValidationError
from hindsight_api.engine.retain import bank_utils


def test_validate_bank_id_rejects_quote_characters():
    with pytest.raises(ValueError, match="quote characters"):
        bank_utils.validate_bank_id('codex::repo"')


def test_validate_bank_id_accepts_repo_style_slug():
    assert bank_utils.validate_bank_id("codex::repo-name") == "codex::repo-name"


@pytest.mark.asyncio
async def test_get_bank_profile_rejects_quoted_bank_id(memory_no_llm_verify, request_context):
    with pytest.raises(OperationValidationError, match="quote characters"):
        await memory_no_llm_verify.get_bank_profile('codex::repo"', request_context=request_context)


@pytest.mark.asyncio
async def test_recall_async_rejects_quoted_bank_id(memory_no_llm_verify, request_context):
    with pytest.raises(OperationValidationError, match="quote characters"):
        await memory_no_llm_verify.recall_async('codex::repo"', "test query", request_context=request_context)


@pytest.mark.asyncio
async def test_retain_batch_async_rejects_quoted_bank_id(memory_no_llm_verify, request_context):
    with pytest.raises(OperationValidationError, match="quote characters"):
        await memory_no_llm_verify.retain_batch_async(
            'codex::repo"',
            contents=[{"content": "test content"}],
            request_context=request_context,
        )
