import os
import subprocess
from concurrent.futures import ThreadPoolExecutor,as_completed
from typing import Dict
import threading

class DeviceScheduler:

    def __init__(self):
        # 在类中设置读写互斥锁，防止多进程读写result冲突情况
        self.lock = threading.Lock()
        self.result = []

    # 线程调用的函数
    def _run_container(self,device_serial:str,timeout_sec:int = 600) -> Dict:
        host_log_path = os.environ.get("HOST_LOG_PATH","/tmp/logs")
        runner_image = os.environ.get("RUNNER_IMAGE","odm_device_runner:v1.0")
        cmd = [
            "docker", "run", "--rm",
            "-e", f"SERIAL={device_serial}",
            "-e", "ADB_SERVER_SOCKET=tcp:host.docker.internal:5037",
            "-v", f"{host_log_path}:/app/log",
            runner_image
        ]
        try:
            subprocess.run(
                cmd,
                timeout=timeout_sec,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return {"device_serial": device_serial, "result": "SUCCESS",'msg':"Test finished successfully"}
        except subprocess.TimeoutExpired as e:
            return {"device_serial": device_serial, "result": "TIMEOUT",'msg':str(e)}
        except subprocess.CalledProcessError as e:
            return {"device_serial": device_serial, "result": "FAIL",'msg':str(e)}
        except Exception as e:
            return {"device_serial": device_serial,"result": "ERROR","msg": str(e)}

    def execute_all(self,devices:list):
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_device = {}
            for device in devices:
                future = executor.submit(self._run_container,device)
                future_to_device[future] = device

            for future in as_completed(future_to_device):
                device = future_to_device[future]
                try:
                    result = future.result()
                    with self.lock:
                        self.result.append(result)
                    print(f"[{device}] 任务完成: {result}")
                except Exception as e:
                    print(f"[{device}] 任务崩溃: {e}")
