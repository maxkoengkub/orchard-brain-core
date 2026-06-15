import pytest
from gateway.configuration.config_manager import ConfigManager

@pytest.fixture
def config_manager():
    return ConfigManager(network_id=1)
