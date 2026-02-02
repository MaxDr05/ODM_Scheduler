import os,time,random
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
        env_type = os.environ.get("ENV_TYPE", "PRODUCTION")

        # ------------------- MOCK 逻辑开始 -------------------
        if env_type == "MOCK":
            # 模拟测试耗时
            time.sleep(random.uniform(1, 3))

            # 伪造日志生成
            # 注意：在 Scheduler 容器内部，日志挂载点固定是 /app/log
            # 不能用 host_log_path (那是宿主机的路径，Python 写不进去)
            internal_log_path = "/app/log"
            log_file = os.path.join(internal_log_path, f"{device_serial}.log")

            try:
                with open(log_file, "w", encoding="utf-8") as f:
                    f.write(f"Start testing device {device_serial}...\n")
                    f.write("Logcat capture started.\n")

                    # 模拟一台设备崩溃 (Crash)，其他设备正常
                    if "FAIL" in device_serial:
                        f.write("FATAL EXCEPTION: main\n")
                        f.write("Process: com.android.phone\n")
                        f.write("java.lang.NullPointerException\n")
                        return {"serial": device_serial, "status": "FAIL", "msg": "Mock Crash Detected"}
                    else:
                        f.write("Test finished successfully.\n")
                        f.write("No errors found.\n")
                        return {"serial": device_serial, "status": "SUCCESS", "msg": "Mock Success"}
            except Exception as e:
                print(f"[Mock Error] Failed to write log: {e}")
                return {"serial": device_serial, "status": "ERROR", "msg": str(e)}
        # ------------------- MOCK 逻辑结束 -------------------

        # 真实 Docker 运行逻辑 (保持不变)
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


if __name__ == "__main__":
    # 如果没传设备列表，就用这组 Mock 设备
    # 包含两台正常，一台会触发 Mock 崩溃的设备
    target_devices = ["Mock_Device_001", "Mock_Device_002", "Mock_Device_FAIL_003"]

    # 实例化并运行
    scheduler = DeviceScheduler()
    scheduler.execute_all(target_devices)