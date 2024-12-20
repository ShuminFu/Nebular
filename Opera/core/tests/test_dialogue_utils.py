import unittest
from uuid import UUID
from Opera.core.dialogue_utils import ProcessingDialogue, DialogueType


class TestProcessingDialogue(unittest.TestCase):
    def setUp(self):
        # 创建测试用的对话实例
        self.test_opera_id = UUID('96028f82-9f76-4372-976c-f0c5a054db79')
        self.test_dialogue = ProcessingDialogue(
            dialogue_index=1,
            opera_id=self.test_opera_id,
            type=DialogueType.NORMAL
        )

    def test_fetch_text_from_api(self):
        # 直接测试实际API调用
        text = self.test_dialogue.text
        self.assertIsInstance(text, str)
        self.assertTrue(len(text) > 0)

    def test_fetch_text_with_invalid_opera_id(self):
        # 测试使用无效的opera_id
        invalid_dialogue = ProcessingDialogue(
            dialogue_index=1,
            opera_id=UUID('91028f82-9f76-4372-976c-f0c5a054db79'),
            type=DialogueType.NORMAL
        )
        text = invalid_dialogue.text
        self.assertEqual(text, "")

    def test_fetch_text_with_invalid_index(self):
        # 测试使用无效的对话索引
        invalid_dialogue = ProcessingDialogue(
            dialogue_index=-1,
            opera_id=self.test_opera_id,
            type=DialogueType.NORMAL
        )
        text = invalid_dialogue.text
        self.assertEqual(text, "")


if __name__ == '__main__':
    unittest.main()
