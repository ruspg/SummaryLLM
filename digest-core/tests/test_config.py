"""
Test configuration classes and methods.
"""
import pytest
import os
from unittest.mock import patch, Mock
from digest_core.config import EWSConfig, Config, LLMConfig, TimeConfig, ObservabilityConfig


class TestEWSConfig:
    """Test EWSConfig class methods."""
    
    def test_get_password_success(self):
        """Test successful password retrieval from environment."""
        with patch.dict(os.environ, {'EWS_PASSWORD': 'test_password'}):
            config = EWSConfig()
            assert config.get_password() == 'test_password'
    
    def test_get_password_failure(self):
        """Test password retrieval failure when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = EWSConfig()
            with pytest.raises(ValueError, match="Environment variable EWS_PASSWORD not set"):
                config.get_password()
    
    def test_get_ntlm_username_with_login_domain(self):
        """Test NTLM username generation with login and domain."""
        config = EWSConfig(user_login="ivanov", user_domain="company.ru")
        assert config.get_ntlm_username() == "ivanov@company.ru"
    
    def test_get_ntlm_username_with_upn(self):
        """Test NTLM username generation with UPN fallback."""
        config = EWSConfig(user_upn="ivanov@company.ru")
        assert config.get_ntlm_username() == "ivanov@company.ru"
    
    def test_get_ntlm_username_failure(self):
        """Test NTLM username generation failure."""
        config = EWSConfig()
        with pytest.raises(ValueError, match="Cannot determine NTLM username"):
            config.get_ntlm_username()
    
    def test_custom_password_env(self):
        """Test password retrieval with custom environment variable."""
        with patch.dict(os.environ, {'CUSTOM_PASSWORD': 'custom_password'}):
            config = EWSConfig(password_env='CUSTOM_PASSWORD')
            assert config.get_password() == 'custom_password'


class TestLLMConfig:
    """Test LLMConfig class methods."""
    
    def test_get_token_success(self):
        """Test successful token retrieval from environment."""
        with patch.dict(os.environ, {'LLM_TOKEN': 'test_token'}):
            config = LLMConfig()
            assert config.get_token() == 'test_token'
    
    def test_get_token_failure(self):
        """Test token retrieval failure when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = LLMConfig()
            with pytest.raises(ValueError, match="Environment variable LLM_TOKEN not set"):
                config.get_token()


class TestConfig:
    """Test main Config class methods."""
    
    def test_get_ews_password_delegation(self):
        """Test that get_ews_password delegates to ews.get_password()."""
        with patch.dict(os.environ, {'EWS_PASSWORD': 'test_password'}):
            config = Config()
            assert config.get_ews_password() == 'test_password'
    
    def test_get_llm_token_delegation(self):
        """Test that get_llm_token delegates to llm.get_token()."""
        with patch.dict(os.environ, {'LLM_TOKEN': 'test_token'}):
            config = Config()
            assert config.get_llm_token() == 'test_token'
    
    def test_config_initialization(self):
        """Test that Config initializes with default sub-configs."""
        config = Config()
        assert isinstance(config.time, TimeConfig)
        assert isinstance(config.ews, EWSConfig)
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.observability, ObservabilityConfig)


class TestTimeConfig:
    """Test TimeConfig class."""
    
    def test_default_values(self):
        """Test default time configuration values."""
        config = TimeConfig()
        assert config.user_timezone == "Europe/Moscow"
        assert config.window == "calendar_day"


class TestObservabilityConfig:
    """Test ObservabilityConfig class."""
    
    def test_default_values(self):
        """Test default observability configuration values."""
        config = ObservabilityConfig()
        assert config.prometheus_port == 9108
        assert config.log_level == "INFO"


class TestConfigIntegration:
    """Integration tests for Config class."""
    
    def test_ews_config_access_chain(self):
        """Test the correct access chain: Config.get_ews_password() -> EWSConfig.get_password()."""
        with patch.dict(os.environ, {'EWS_PASSWORD': 'integration_test_password'}):
            config = Config()
            
            # Test that Config.get_ews_password() works
            password = config.get_ews_password()
            assert password == 'integration_test_password'
            
            # Test that EWSConfig.get_password() also works
            ews_password = config.ews.get_password()
            assert ews_password == 'integration_test_password'
            
            # Ensure they return the same value
            assert password == ews_password
    
    def test_llm_config_access_chain(self):
        """Test the correct access chain: Config.get_llm_token() -> LLMConfig.get_token()."""
        with patch.dict(os.environ, {'LLM_TOKEN': 'integration_test_token'}):
            config = Config()
            
            # Test that Config.get_llm_token() works
            token = config.get_llm_token()
            assert token == 'integration_test_token'
            
            # Test that LLMConfig.get_token() also works
            llm_token = config.llm.get_token()
            assert llm_token == 'integration_test_token'
            
            # Ensure they return the same value
            assert token == llm_token
