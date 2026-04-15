from incalmo.core.strategies.llm.langchain_strategy import LangChainStrategy
from incalmo.core.strategies.llm.interfaces.langchain_interface import (
    LangChainInterface,
)
from incalmo.core.strategies.llm.interfaces.llm_interface import LLMInterface
from incalmo.core.actions import LowLevel
from config.attacker_config import AttackerConfig

_API_TESTING_ACTIONS = {
    # Network discovery
    "ScanNetwork",
    "ScanHost",
    # HTTP / API testing
    "HTTPRequest",
    "HTTPRequestWithToken",
    "OAuthClientCredentials",
    "HTTPMethodFuzz",
    "APIEndpointProbe",
    "BrokenObjectLevelAuth",
    "MissingFunctionLevelAuth",
    "FuzzAPIParameter",
}


class APITestingStrategy(LangChainStrategy, name="api_testing"):
    """LangChain strategy restricted to API/microservice testing actions only.

    Exposes only the HTTP action classes in the LLM's exec() context, preventing
    host-level actions (SSHLateralMove, ExploitStruts, etc.) from being reachable.
    """

    def get_action_classes(self) -> dict:
        return {
            name: getattr(LowLevel, name)
            for name in _API_TESTING_ACTIONS
            if hasattr(LowLevel, name)
        }
