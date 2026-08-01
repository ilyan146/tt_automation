from tt_automation.config import Settings


def test_blank_openai_key_is_treated_as_missing() -> None:
    settings = Settings(openai_api_key="   ")

    assert settings.openai_api_key is None
