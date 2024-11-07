import requests
import uuid
from datetime import datetime
import pytest
import json
from models import (
    OperaForCreation, BotForCreation, StaffForCreation,
    StageForCreation, DialogueForCreation, StaffInvitationForCreation,
    ResourceForCreation, OperaPropertyForUpdate,
    OperaWithMaintenanceState, Bot, Staff, Stage, Dialogue, StaffInvitation, Resource, OperaProperty,
    BotForUpdate, StaffForUpdate, ResourceForUpdate, StaffForFilter, ResourceForFilter,
    DialogueForFilter
)

BASE_URL = "http://opera.nti56.com"

class TestOperaAPI:
    def __init__(self):


    def setup_class(self):
        self.session = requests.Session()
        # 用于存储测试过程中创建的资源ID
        self.test_opera_id = None
        self.test_bot_id = None
        self.test_staff_id = None
        self.test_resource_id = None
        self.test_invitation_id = None
        self.temp_file_id = None

    def test_01_create_opera(self):
        """测试创建Opera"""
        url = f"{BASE_URL}/Opera"
        data = OperaForCreation(
            name="测试Opera",
            description="这是一个测试Opera",
            database_name="test_db"
        ).model_dump(by_alias=True)
        response = self.session.post(url, json=data)
        assert response.status_code == 201
        result = response.json()
        TestOperaAPI.test_opera_id = result["id"]
        assert result["name"] == data["Name"]

    def test_02_create_bot(self):
        """测试创建Bot"""
        url = f"{BASE_URL}/Bot"
        data = BotForCreation(
            name="测试Bot",
            description="这是一个测试Bot",
            call_shell_on_opera_started=None,
            default_tags="test",
            default_roles="user",
            default_permissions="read"
        ).model_dump(by_alias=True)
        response = self.session.post(url, json=data)
        assert response.status_code == 201
        result = response.json()
        TestOperaAPI.test_bot_id = result["id"]
        assert result["name"] == data["Name"]

    def test_03_create_staff(self):
        """测试创建Staff"""
        url = f"{BASE_URL}/Opera/{self.test_opera_id}/Staff"
        data = StaffForCreation(
            bot_id=self.test_bot_id,
            name="测试Staff",
            parameter=json.dumps({"name": "monkey"}),
            is_on_stage=True,
            tags="test",
            roles="user",
            permissions="read"
        ).model_dump(by_alias=True)
        response = self.session.post(url, json=data)
        assert response.status_code == 201
        result = response.json()
        TestOperaAPI.test_staff_id = result["id"]
        assert result["name"] == data["Name"]

    def test_04_create_stage(self):
        """测试创建Stage"""
        url = f"{BASE_URL}/Opera/{self.test_opera_id}/Stage"
        data = StageForCreation(
            name="测试场景"
        ).model_dump(by_alias=True)
        response = self.session.post(url, json=data)
        assert response.status_code == 201
        result = response.json()
        assert result["name"] == data["Name"]

    def test_05_create_dialogue(self):
        """测试创建对话"""
        url = f"{BASE_URL}/Opera/{self.test_opera_id}/Dialogue"
        data = DialogueForCreation(
            is_stage_index_null=False,
            staff_id=self.test_staff_id,
            is_narratage=False,
            is_whisper=False,
            text="这是一条测试对话",
            tags="test"
        ).model_dump(by_alias=True)
        response = self.session.post(url, json=data)
        assert response.status_code == 201
        result = response.json()
        assert result["text"] == data["Text"]

    def test_06_create_invitation(self):
        """测试创建邀请"""
        url = f"{BASE_URL}/Opera/{self.test_opera_id}/StaffInvitation"
        data = StaffInvitationForCreation(
            bot_id=self.test_bot_id,
            parameter=json.dumps({"invite_key": "invite_value"}),
            tags="test",
            roles="user",
            permissions="read"
        ).model_dump(by_alias=True)
        response = self.session.post(url, json=data)
        assert response.status_code == 201
        result = response.json()
        TestOperaAPI.test_invitation_id = result["id"]

    def test_07_upload_temp_file(self):
        """测试上传临时文件"""
        url = f"{BASE_URL}/TempFile"
        file_content = b"This is a test file content"
        response = self.session.post(url, data=file_content)
        assert response.status_code == 200
        result = response.json()
        assert result["length"] == len(file_content)
        TestOperaAPI.temp_file_id = result["id"]

    def test_08_create_resource(self):
        """测试创建资源"""
        url = f"{BASE_URL}/Opera/{self.test_opera_id}/Resource"
        data = ResourceForCreation(
            name="测试资源",
            description="这是一个测试资源",
            mime_type="text/plain",
            last_update_staff_name="测试Staff",
            temp_file_id=self.temp_file_id
        ).model_dump(by_alias=True)
        response = self.session.post(url, json=data)
        assert response.status_code == 201
        result = response.json()
        TestOperaAPI.test_resource_id = result["id"]
        assert result["name"] == data["Name"]

    def test_09_update_property(self):
        """测试更新属性"""
        url = f"{BASE_URL}/Opera/{self.test_opera_id}/Property"
        data = OperaPropertyForUpdate(
            properties={"test_key": "test_value"}
        ).model_dump(by_alias=True)
        response = self.session.put(url, json=data)
        assert response.status_code == 204



    def test_11_get_opera(self):
        """测试获取Opera详情"""
        url = f"{BASE_URL}/Opera/{self.test_opera_id}"
        response = self.session.get(url)
        assert response.status_code == 200
        OperaWithMaintenanceState(**response.json())  # 验证响应数据格式

    def test_12_update_bot(self):
        """测试更新Bot"""
        url = f"{BASE_URL}/Bot/{self.test_bot_id}"
        data = BotForUpdate(
            name="更新后的Bot",
            is_description_updated=True,
            description="更新后的描述",
            is_call_shell_on_opera_started_updated=False,
            is_default_tags_updated=True,
            default_tags="updated",
            is_default_roles_updated=False,
            is_default_permissions_updated=False
        ).model_dump(by_alias=True)
        response = self.session.put(url, json=data)
        assert response.status_code == 204

    def test_13_update_staff(self):
        """测试更新Staff"""
        url = f"{BASE_URL}/Opera/{self.test_opera_id}/Staff/{self.test_staff_id}"
        data = StaffForUpdate(
            is_on_stage=False,
            parameter=json.dumps({"updated_key": "updated_value"})
        ).model_dump(by_alias=True)
        response = self.session.put(url, json=data)
        assert response.status_code == 204

    def test_14_filter_staff(self):
        """测试Staff筛选"""
        url = f"{BASE_URL}/Opera/{self.test_opera_id}/Staff"
        params = StaffForFilter(
            name_like="测试",
            is_on_stage=True
        ).model_dump(by_alias=True)
        response = self.session.get(url, params=params)
        assert response.status_code == 200
        result = response.json()
        assert isinstance(result, list)
        for staff in result:
            Staff(**staff)  # 验证每个响应项的数据格式

    def test_15_filter_dialogues(self):
        """测试对话筛选"""
        url = f"{BASE_URL}/Opera/{self.test_opera_id}/Dialogue"
        params = DialogueForFilter(
            top_limit=10,
            includes_stage_index_null=True,
            includes_narratage=True,
            includes_staff_id_null=False
        ).model_dump(by_alias=True)
        response = self.session.get(url, params=params)
        assert response.status_code == 200
        result = response.json()
        assert isinstance(result, list)
        for dialogue in result:
            Dialogue(**dialogue)

    def test_16_filter_resources(self):
        """测试资源筛选"""
        url = f"{BASE_URL}/Opera/{self.test_opera_id}/Resource"
        params = ResourceForFilter(
            name_like="测试",
            mime_type="text/plain",
            last_update_staff_name_like="Staff"
        ).model_dump(by_alias=True)
        response = self.session.get(url, params=params)
        assert response.status_code == 200
        result = response.json()
        assert isinstance(result, list)
        for resource in result:
            Resource(**resource)

    def test_17_update_resource(self):
        """测试更新资源"""
        url = f"{BASE_URL}/Opera/{self.test_opera_id}/Resource/{self.test_resource_id}"
        data = ResourceForUpdate(
            name="更新后的资源",
            description="更新后的描述",
            last_update_staff_name="更新Staff"
        ).model_dump(by_alias=True)
        response = self.session.put(url, json=data)
        assert response.status_code == 204

    def test_18_get_opera_property(self):
        """测试获取Opera属性"""
        url = f"{BASE_URL}/Opera/{self.test_opera_id}/Property"
        response = self.session.get(url)
        assert response.status_code == 200
        OperaProperty(**response.json())

    def test_10_cleanup(self):
        """清理测试数据"""
        # 删除Resource
        if self.test_resource_id:
            url = f"{BASE_URL}/Opera/{self.test_opera_id}/Resource/{self.test_resource_id}"
            response = self.session.delete(url)
            assert response.status_code == 204

        # 删除Staff
        if self.test_staff_id:
            url = f"{BASE_URL}/Opera/{self.test_opera_id}/Staff/{self.test_staff_id}"
            response = self.session.delete(url)
            assert response.status_code == 200

        # 删除Invitation
        if self.test_invitation_id:
            url = f"{BASE_URL}/Opera/{self.test_opera_id}/StaffInvitation/{self.test_invitation_id}"
            response = self.session.delete(url)
            assert response.status_code == 204

        # 删除Bot
        if self.test_bot_id:
            url = f"{BASE_URL}/Bot/{self.test_bot_id}"
            response = self.session.delete(url)
            assert response.status_code == 204

        # 删除Opera
        if self.test_opera_id:
            url = f"{BASE_URL}/Opera/{self.test_opera_id}"
            response = self.session.delete(url)
            assert response.status_code == 204
if __name__ == "__main__":
    pytest.main(["-v", "test_api.py"]) 