from crewai.flow.flow import Flow, listen, start, router, or_
from typing import Dict, List
from pydantic import BaseModel, Field
from src.core.logger_config import get_logger_with_trace_id
from src.crewai_ext.crew_bases.manager_crewbase import ManagerInitCrew
from pathlib import Path
import yaml

logger = get_logger_with_trace_id()


class InitState(BaseModel):
    """配置生成流程状态"""

    config: Dict[str, List[Dict]] = Field(default_factory=lambda: {"runners": [{"agents": {}, "tasks": {}}]})
    validation_passed: bool = False
    error_messages: Dict[str, str] = {}
    current_step: str = "init"


class ManagerInitFlow(Flow[InitState]):
    """Crew配置生成流程

    根据用户对话需求生成CrewRunner的配置
    包含agents和tasks的完整配置生成
    """

    def __init__(self, query: str):
        super().__init__()
        self.query = query
        self.config_crew = ManagerInitCrew()
        self.log = get_logger_with_trace_id()

        # 加载默认配置
        self.default_agents = self._load_default_config("../config/crew_runner/agents.yaml")
        self.default_tasks = self._load_default_config("../config/crew_runner/tasks.yaml")

    def _load_default_config(self, config_path: str) -> dict:
        """加载默认YAML配置"""
        try:
            base_dir = Path(__file__).parent
            full_path = base_dir.joinpath(config_path).resolve()
            with open(full_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.log.warning(f"加载默认配置失败: {str(e)}")
            return {}

    @start()
    def start_flow(self):
        """初始化配置生成流程"""
        # 使用默认配置作为基础
        self.state.config = {
            "runners": [{"agents": self.default_agents.copy(), "tasks": self.default_tasks.copy()}],
            "validation": {"passed": False},
        }
        self.state.current_step = "need_generate_configs"

    @listen("route_generate_configs")
    async def generate_configs(self):
        """解析用户需求生成配置骨架"""
        try:
            # 调用配置生成Crew
            if self.state.error_messages:
                inputs = {
                    "query": f"{self.query}\n[ERRORS]: {self.state.error_messages}\n[CURRENT_CONFIG]: {self.state.config}",
                    "num_runners": 3,
                }
            else:
                inputs = {"query": self.query, "num_runners": 3}

            result = await self.config_crew.crew().kickoff_async(inputs=inputs)

            # 解析生成的配置骨架
            self._parse_config_skeleton(result.raw)
            self.state.current_step = "need_validate_configs"

        except Exception as e:
            self.log.error(f"需求解析失败: {str(e)}")
            self.state.error_messages["parsing"] = str(e)
            self.state.current_step = "need_generate_configs"

    @listen("route_validate_configs")
    async def validate_configuration(self):
        """执行配置验证"""
        try:
            self._validate_config()
            self.state.current_step = "need_output_config"
            self.state.config["validation"] = {"passed": True}
            self.log.info("配置验证通过")
        except ValueError as e:
            self.log.error(f"配置验证失败: {str(e)}")
            self.state.error_messages["validation"] = str(e)
            self.state.current_step = "need_generate_configs"

    @router(or_(generate_configs, validate_configuration, start_flow))
    def route_config_generation(self):
        """路由配置生成流程"""
        if self.state.current_step == "need_generate_configs":
            return "route_generate_configs"
        elif self.state.current_step == "need_validate_configs":
            return "route_validate_configs"
        elif self.state.current_step == "need_output_config":
            return "route_output_config"
        return "route_error_handling"

    @listen("route_output_config")
    async def output_configuration(self):
        """输出最终配置"""
        self.log.info(f"最终配置: {self.state.config}")
        return self.state.config

    def _parse_config_skeleton(self, raw_config: str):
        """解析配置骨架（合并默认配置）"""
        import json
        from json.decoder import JSONDecodeError

        try:
            if raw_config.startswith("```json"):
                raw_config = raw_config[7:-3].strip()

            skeleton = json.loads(raw_config)

            # 深度合并配置
            def deep_merge(base, update):
                for k, v in update.items():
                    if isinstance(v, dict) and k in base:
                        base[k] = deep_merge(base.get(k, {}), v)
                    else:
                        base[k] = v
                return base

            # 合并生成的骨架配置到默认配置
            for i, runner in enumerate(skeleton.get("runners", [])):
                if i >= len(self.state.config["runners"]):
                    self.state.config["runners"].append({"agents": {}, "tasks": {}})

                # 深度合并每个runner的配置
                self.state.config["runners"][i]["agents"] = deep_merge(
                    self.state.config["runners"][i]["agents"], runner.get("agents", {})
                )
                self.state.config["runners"][i]["tasks"] = deep_merge(
                    self.state.config["runners"][i]["tasks"], runner.get("tasks", {})
                )

        except JSONDecodeError:
            self.log.error("配置骨架解析失败")
            raise

    def _validate_config(self):
        """验证配置完整性"""
        if not self.state.config.get("runners"):
            raise ValueError("至少需要配置一个CrewRunner")

        for i, runner in enumerate(self.state.config["runners"]):
            if not runner.get("agents"):
                raise ValueError(f"Runner {i + 1} 缺少agents配置")
            if not runner.get("tasks"):
                raise ValueError(f"Runner {i + 1} 缺少tasks配置")

        self.state.validation_passed = True
