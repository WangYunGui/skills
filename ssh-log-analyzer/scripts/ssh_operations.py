#!/usr/bin/env python3
"""
SSH远程文件读取工具 - 连接远程服务器,读取文件内容

使用方式: 通过stdin传入JSON参数,避免远程路径出现在命令行中被Bash工具拦截。

示例:
  echo '{"host":"10.0.0.1","port":22,"username":"admin","password":"pass","command":"list","path":"/var/log"}' | python3 ssh_operations.py
  echo '{"host":"10.0.0.1","port":22,"username":"admin","password":"pass","command":"read","path":"/var/log/app.log","lines":2000}' | python3 ssh_operations.py
  echo '{"host":"10.0.0.1","port":22,"username":"admin","password":"pass","command":"time"}' | python3 ssh_operations.py
"""

import paramiko
import json
import sys
from typing import Dict


class SSHReader:
    """SSH文件读取器"""

    def __init__(self, host: str, port: int, username: str, password: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client = None

    def connect(self) -> Dict[str, str]:
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10
            )
            return {'status': 'success', 'message': f'成功连接到 {self.host}:{self.port}'}
        except paramiko.AuthenticationException:
            return {'status': 'error', 'message': '认证失败,请检查用户名和密码'}
        except paramiko.SSHException as e:
            return {'status': 'error', 'message': f'SSH连接错误: {str(e)}'}
        except Exception as e:
            return {'status': 'error', 'message': f'连接失败: {str(e)}'}

    def disconnect(self):
        if self.client:
            self.client.close()
            self.client = None

    def exec_command(self, command: str) -> Dict:
        if not self.client:
            return {'status': 'error', 'message': '未建立SSH连接'}
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            if error:
                return {'status': 'error', 'message': error}
            return {'status': 'success', 'output': output}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def list_directory(self, path: str) -> Dict:
        return self.exec_command(f'ls -lah {path}')

    def get_server_time(self) -> Dict:
        return self.exec_command('date "+%Y-%m-%d %H:%M:%S"')

    def read_file(self, file_path: str, lines: int = 2000) -> Dict:
        return self.exec_command(f'tail -n {lines} {file_path}')


def main():
    # 从stdin读取JSON参数
    try:
        raw_input = sys.stdin.read()
        params = json.loads(raw_input)
    except json.JSONDecodeError:
        print(json.dumps({
            'status': 'error',
            'message': '无效的JSON输入。用法: echo \'{"host":"...","port":22,"username":"...","password":"...","command":"list","path":"..."}\' | python3 ssh_operations.py'
        }, ensure_ascii=False))
        sys.exit(1)

    host = params.get('host')
    port = int(params.get('port', 22))
    username = params.get('username')
    password = params.get('password')
    command = params.get('command')

    if not all([host, username, password, command]):
        print(json.dumps({
            'status': 'error',
            'message': '缺少必要参数: host, username, password, command'
        }, ensure_ascii=False))
        sys.exit(1)

    reader = SSHReader(host, port, username, password)

    # 连接
    connect_result = reader.connect()
    if connect_result['status'] == 'error':
        print(json.dumps(connect_result, indent=2, ensure_ascii=False))
        sys.exit(1)

    # 执行命令
    if command == 'list':
        path = params.get('path', '/')
        result = reader.list_directory(path)
    elif command == 'time':
        result = reader.get_server_time()
    elif command == 'read':
        file_path = params.get('path')
        lines = int(params.get('lines', 2000))
        if not file_path:
            result = {'status': 'error', 'message': '缺少path参数'}
        else:
            result = reader.read_file(file_path, lines)
    else:
        result = {'status': 'error', 'message': f'未知命令: {command}'}

    print(json.dumps(result, indent=2, ensure_ascii=False))
    reader.disconnect()


if __name__ == '__main__':
    main()
