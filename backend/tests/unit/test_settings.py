from app.config.settings import Settings


class TestSettingsParsing:
    def test_debug_accepts_release_string(self):
        settings = Settings(debug="release")
        assert settings.debug is False

    def test_debug_accepts_development_string(self):
        settings = Settings(debug="development")
        assert settings.debug is True

    def test_cors_origins_accepts_comma_separated_string(self):
        settings = Settings(cors_origins="http://localhost:5173, http://127.0.0.1:5173")
        assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]
