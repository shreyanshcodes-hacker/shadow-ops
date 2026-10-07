from typing import Dict, Optional, Type, List
from app.agents.team.base import TeamBaseAgent
from app.agents.team.recon import ReconAgent
from app.agents.team.vulnerability_analyst import VulnerabilityAnalystAgent
from app.agents.team.attack_path_analyst import AttackPathAnalystAgent
from app.agents.team.risk_analyst import RiskAnalystAgent
from app.agents.team.security_reviewer import SecurityReviewerAgent
from app.ai.providers import AIProvider
from app.ai.team_schemas import AgentName


class TeamAgentRegistry:
    """Centralized registry for Security Team agents."""
    
    def __init__(self):
        self._agent_classes: Dict[AgentName, Type[TeamBaseAgent]] = {}
        self._instances: Dict[AgentName, TeamBaseAgent] = {}
    
    def register(self, agent_class: Type[TeamBaseAgent]) -> None:
        self._agent_classes[agent_class.name] = agent_class
    
    def get_class(self, name: AgentName) -> Optional[Type[TeamBaseAgent]]:
        return self._agent_classes.get(name)
    
    def get_instance(self, name: AgentName, provider: AIProvider) -> TeamBaseAgent:
        """Get or create agent instance with provider."""
        if name not in self._instances:
            agent_class = self.get_class(name)
            if not agent_class:
                raise ValueError(f"Agent {name} not registered")
            self._instances[name] = agent_class(provider)
        return self._instances[name]
    
    def all_classes(self) -> Dict[AgentName, Type[TeamBaseAgent]]:
        return self._agent_classes.copy()
    
    def all_names(self) -> List[AgentName]:
        return list(self._agent_classes.keys())
    
    def execution_order(self) -> List[AgentName]:
        """Return agents in dependency order."""
        return [
            AgentName.RECON,
            AgentName.VULNERABILITY_ANALYST,
            AgentName.ATTACK_PATH_ANALYST,
            AgentName.RISK_ANALYST,
            AgentName.SECURITY_REVIEWER,
        ]
    
    def dependencies(self) -> Dict[AgentName, List[AgentName]]:
        """Return agent dependencies."""
        return {
            AgentName.RECON: [],
            AgentName.VULNERABILITY_ANALYST: [AgentName.RECON],
            AgentName.ATTACK_PATH_ANALYST: [AgentName.RECON, AgentName.VULNERABILITY_ANALYST],
            AgentName.RISK_ANALYST: [AgentName.RECON, AgentName.VULNERABILITY_ANALYST, AgentName.ATTACK_PATH_ANALYST],
            AgentName.SECURITY_REVIEWER: [
                AgentName.RECON,
                AgentName.VULNERABILITY_ANALYST,
                AgentName.ATTACK_PATH_ANALYST,
                AgentName.RISK_ANALYST,
            ],
        }
    
    def can_run_parallel(self, agent_a: AgentName, agent_b: AgentName) -> bool:
        """Check if two agents can run in parallel (no dependency)."""
        deps = self.dependencies()
        return agent_a not in deps.get(agent_b, []) and agent_b not in deps.get(agent_a, [])


# Global registry instance
team_agent_registry = TeamAgentRegistry()

# Register all agents
team_agent_registry.register(ReconAgent)
team_agent_registry.register(VulnerabilityAnalystAgent)
team_agent_registry.register(AttackPathAnalystAgent)
team_agent_registry.register(RiskAnalystAgent)
team_agent_registry.register(SecurityReviewerAgent)


def get_team_agent_class(name: AgentName) -> Type[TeamBaseAgent]:
    agent = team_agent_registry.get_class(name)
    if not agent:
        raise ValueError(f"Team agent {name} not registered")
    return agent


def get_team_agent_instance(name: AgentName, provider: AIProvider) -> TeamBaseAgent:
    return team_agent_registry.get_instance(name, provider)
