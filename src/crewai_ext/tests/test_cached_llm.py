import unittest
import os
import time
import shutil

from crewai import Agent, Task, Crew, Process
import litellm
from litellm.caching import Cache
from src.crewai_ext.config.llm_setup import test_config
from src.crewai_ext.config.llm_factory import get_llm


class TestCrewAIWithCache(unittest.TestCase):
    """测试在CrewAI中使用LiteLLM缓存"""

    def setUp(self):
        """测试开始前清理缓存"""
        self.cache_dir = '.test_cache'
        if os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)

        # 创建带缓存的LLM模型
        self.llm = get_llm(
            use_cache=True,
            cache_dir=self.cache_dir,
            model="azure/gpt-4o",
            api_key=os.environ.get("AZURE_API_KEY"),
            base_url=os.environ.get("AZURE_API_BASE")
        )

    def tearDown(self):
        """测试结束后清理缓存"""
        if os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)
        litellm.disable_cache()

    def test_crewai_with_cache(self):
        """测试CrewAI场景中的LLM缓存"""
        # 创建前端架构专家agent
        frontend_expert = Agent(
            name=test_config['agents'][0]['name'],
            role=test_config['agents'][0]['role'],
            goal=test_config['agents'][0]['goal'],
            backstory=test_config['agents'][0]['backstory'],
            llm=self.llm
        )

        # 创建UI交互专家agent
        ui_expert = Agent(
            name=test_config['agents'][1]['name'],
            role=test_config['agents'][1]['role'],
            goal=test_config['agents'][1]['goal'],
            backstory=test_config['agents'][1]['backstory'],
            llm=self.llm
        )

        # 创建前端开发任务
        frontend_task = Task(
            description='''设计一个现代化的前端项目结构，包括：
            1. 目录结构
            2. 核心依赖选择
            3. 构建工具配置
            4. 代码规范设置''',
            agent=frontend_expert,
            expected_output="一份完整的前端项目架构设计文档，包含目录结构、依赖选择、构建配置和代码规范"
        )

        # 创建UI设计任务
        ui_task = Task(
            description='''基于前端架构设计，规划UI组件库：
            1. 核心组件列表
            2. 组件交互规范
            3. 主题系统设计
            4. 响应式策略''',
            agent=ui_expert,
            expected_output="一份详细的UI组件库规划文档，包含组件列表、交互规范、主题系统和响应式策略"
        )

        # 创建crew
        crew = Crew(
            agents=[frontend_expert, ui_expert],
            tasks=[frontend_task, ui_task],
            process=Process.sequential,
            verbose=True
        )

        # 第一次运行（应该调用API）
        print("CrewAI测试 - 第一次运行")
        result1 = crew.kickoff()

        # 验证缓存文件已创建
        self.assertTrue(len(os.listdir(self.cache_dir)) > 0)

        # 第二次运行（应该使用缓存）
        print("CrewAI测试 - 第二次运行（应该使用缓存）")
        result2 = crew.kickoff()

        # 验证两次结果相同（只比较生成的内容）
        def get_content(result):
            return '\n'.join([
                line for line in str(result).split('\n')
                if not any(x in line.lower() for x in ['tokens', 'requests', 'usage'])
            ])

        self.assertEqual(get_content(result1), get_content(result2))

    def test_different_prompts(self):
        """测试不同提示词生成不同的缓存"""
        # 创建两个不同的前端专家
        expert1 = Agent(
            name="React专家",
            role="前端架构师",
            goal="设计React项目架构",
            backstory="专注于React技术栈的前端架构师",
            llm=self.llm
        )

        expert2 = Agent(
            name="Vue专家",
            role="前端架构师",
            goal="设计Vue项目架构",
            backstory="专注于Vue技术栈的前端架构师",
            llm=self.llm
        )

        # 创建相似但不同框架的任务
        task1 = Task(
            description="设计一个React项目的最佳实践架构",
            agent=expert1,
            expected_output="一份完整的React项目架构设计文档，包含项目结构、状态管理、路由设计等最佳实践"
        )

        task2 = Task(
            description="设计一个Vue项目的最佳实践架构",
            agent=expert2,
            expected_output="一份完整的Vue项目架构设计文档，包含项目结构、状态管理、路由设计等最佳实践"
        )

        # 创建两个crew
        crew1 = Crew(
            agents=[expert1],
            tasks=[task1],
            process=Process.sequential
        )

        crew2 = Crew(
            agents=[expert2],
            tasks=[task2],
            process=Process.sequential
        )

        # 运行并验证生成不同的缓存
        result1 = crew1.kickoff()
        result2 = crew2.kickoff()

        # 由于是不同的框架和专家，应该生成不同的缓存键
        cache_files = os.listdir(self.cache_dir)
        self.assertGreater(len(cache_files), 1)

    def test_cache_expiration(self):
        """测试缓存过期功能"""
        # 创建一个短期缓存的LLM
        short_llm = get_llm(
            use_cache=True,
            cache_dir=self.cache_dir,
            model="azure/gpt-4o",
            api_key=os.environ.get("AZURE_API_KEY"),
            base_url=os.environ.get("AZURE_API_BASE")
        )

        # 配置短期缓存
        litellm.cache = Cache(
            type="disk",
            ttl=1,  # 1秒后过期
            disk_cache_dir=self.cache_dir
        )
        litellm.enable_cache()

        # 创建agent
        agent = Agent(
            name="性能优化专家",
            role="前端性能专家",
            goal="优化前端性能",
            backstory="专注于前端性能优化的专家",
            llm=short_llm
        )

        # 创建任务
        task = Task(
            description="分析并提供前端性能优化建议",
            agent=agent,
            expected_output="一份详细的前端性能优化报告，包含性能瓶颈分析和具体优化建议"
        )

        # 创建crew
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential
        )

        # 第一次运行
        result1 = crew.kickoff()

        # 等待缓存过期
        time.sleep(2)

        # 第二次运行（应该重新调用API）
        result2 = crew.kickoff()

        # 结果应该不同（因为缓存已过期）
        self.assertNotEqual(result1, result2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
