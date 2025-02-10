import os
import unittest
import tempfile
import threading
from swarmclone.config import GlobalConfig, config, reset_config

class TestGlobalConfig(unittest.TestCase):
    def setUp(self):
        # 创建临时配置文件
        self.temp_config = tempfile.NamedTemporaryFile(mode='w+', delete=False)
        self.temp_config.write("""
        [panel.server]
        host = "127.0.0.1"
        port = 7624

        [llm]
        port = 7621
        """)
        self.temp_config.flush()
        self.temp_config.close()
        
        # 重置单例并更新配置路径
        reset_config()
        # 使用实例的 CONFIG_FILE 属性
        config.CONFIG_FILE = self.temp_config.name
        config.reload_config()

    def tearDown(self):
        os.remove(self.temp_config.name)

    def test_singleton_pattern(self):
        """测试单例模式"""
        self.assertIs(config, config)
        new_instance = GlobalConfig()
        self.assertIsNot(config, new_instance)

    def test_default_values(self):
        """测试默认配置值"""
        self.assertEqual(config.NUM_WORKERS, 4)
        self.assertEqual(config.DEVICE, "cuda")
        self.assertListEqual(config.START_ASR_COMMAND, ["python", "-m", "swarmclone.asr"])

    def test_toml_loading(self):
        """测试TOML配置加载"""
        self.assertEqual(config.panel.server.port, 7624)
        self.assertEqual(config.llm.port, 7621)
        self.assertEqual(config.panel.server.host, "127.0.0.1")

    def test_config_reloading(self):
        """测试配置热重载"""
        with open(self.temp_config.name, 'w') as f:
            f.write("""
            [panel.server]
            port = 9999
            """)
            f.flush()  # 确保内容写入文件
            os.fsync(f.fileno())  # 确保数据写入磁盘

        config.reload_config()
        self.assertEqual(config.panel.server.port, 9999)

    def test_multithread_access(self):
        """测试多线程安全访问"""
        results = []
        barrier = threading.Barrier(5)
        
        def worker():
            barrier.wait()
            results.append(config.panel.server.port)
        
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(len(results), 5)
        self.assertTrue(all(x == 7624 for x in results))

