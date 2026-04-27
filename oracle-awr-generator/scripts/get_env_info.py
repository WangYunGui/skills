#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Oracle服务器信息查询脚本
通过调用接口获取Oracle数据库连接信息
接口: POST /dmpp/asset/assetCredentialsList

接口返回字段映射:
- resourceIpAddress -> 连接串，支持两种格式:
    1) JDBC URL: jdbc:oracle:thin:@//172.16.22.232:1521/cc
    2) 简写格式: 172.16.22.232:1521/cc
- username -> 用户名
- password -> 密码
- envName -> 环境名称

ipPort和resourceLocation字段已废弃，所有连接信息统一在resourceIpAddress中。
hostAppName固定为"Oracle"。

@author wang.peiwei 2026-04-27
"""

import sys
import json
import re
import ssl
import urllib.request
import urllib.error


def parse_resource_ip_address(raw):
    """
    从resourceIpAddress字段解析出IP、端口、服务名

    支持两种格式:
    1) JDBC URL: jdbc:oracle:thin:@//172.16.22.232:1521/cc
    2) 简写格式: 172.16.22.232:1521/cc

    Args:
        raw: resourceIpAddress原始字符串

    Returns:
        dict: {ip, port, service_name, jdbc_url}，解析失败返回None
    """
    if not raw:
        return None

    # 去掉JDBC URL前缀，只保留 host:port/service 部分
    conn_str = raw.strip()
    jdbc_prefix_pattern = r'^jdbc:oracle:thin:@//'
    if re.match(jdbc_prefix_pattern, conn_str):
        conn_str = re.sub(jdbc_prefix_pattern, '', conn_str)

    # 解析 host:port/service_name
    # 格式: <ip_or_host>:<port>/<service_name>
    match = re.match(r'^([^:/]+):(\d+)/([^/]+)$', conn_str)
    if not match:
        return None

    ip = match.group(1)
    port = match.group(2)
    service_name = match.group(3)
    jdbc_url = f"jdbc:oracle:thin:@//{ip}:{port}/{service_name}"

    return {
        'ip': ip,
        'port': port,
        'service_name': service_name,
        'jdbc_url': jdbc_url
    }


def get_env_info(project_id):
    """
    获取Oracle数据库服务器连接信息

    Args:
        project_id: 项目ID, 从project.json中获取

    Returns:
        list: 包含服务器信息的列表(可能多个), 每项包含jdbcUrl、userName、pwd、envName,
              如果查询失败返回空列表
    """
    try:
        # 构建请求URL和Body
        base_url = "https://edo.iwhalecloud.com/dmpp/asset/assetCredentialsList"

        # 构建JSON请求体 - hostAppName固定为Oracle
        request_body = {
            "hostAppName": "Oracle",
            "projectId": project_id
        }

        # 发送POST请求 (JSON body)
        req = urllib.request.Request(
            base_url,
            data=json.dumps(request_body).encode('utf-8'),
            method='POST'
        )
        req.add_header('Accept', 'application/json')
        req.add_header('Content-Type', 'application/json')

        with urllib.request.urlopen(req, timeout=10, context=ssl._create_unverified_context()) as response:
            data = json.loads(response.read().decode('utf-8'))

            # 检查返回数据格式
            if data and data.get('resultCode') == '0' and data.get('resultData'):
                result_list = []
                for item in data.get('resultData', []):
                    # 从resourceIpAddress解析IP、端口、服务名
                    raw_addr = item.get('resourceIpAddress', '')
                    parsed = parse_resource_ip_address(raw_addr)
                    if not parsed:
                        continue  # 解析失败，跳过该条目

                    server_info = {
                        'jdbcUrl': parsed['jdbc_url'],
                        'userName': item.get('username', ''),
                        'pwd': item.get('password', ''),
                        'envName': item.get('envName', ''),
                        'hostAppName': item.get('hostAppName', '')
                    }
                    # 检查必要字段是否存在(jdbcUrl, userName, pwd必须非空)
                    if all(key in server_info and server_info[key] for key in ['jdbcUrl', 'userName', 'pwd']):
                        result_list.append(server_info)
                return result_list
            else:
                return []

    except urllib.error.HTTPError as e:
        print(json.dumps({
            'error': f'HTTP错误: {e.code}',
            'message': str(e)
        }, ensure_ascii=False))
        return []
    except urllib.error.URLError as e:
        print(json.dumps({
            'error': '网络连接错误',
            'message': str(e.reason)
        }, ensure_ascii=False))
        return []
    except json.JSONDecodeError as e:
        print(json.dumps({
            'error': 'JSON解析错误',
            'message': str(e)
        }, ensure_ascii=False))
        return []
    except Exception as e:
        print(json.dumps({
            'error': '未知错误',
            'message': str(e)
        }, ensure_ascii=False))
        return []


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print(json.dumps({
            'error': '参数错误',
            'message': '请提供项目ID作为参数'
        }, ensure_ascii=False))
        sys.exit(1)

    project_id = sys.argv[1]

    result = get_env_info(project_id)

    # 输出JSON格式结果
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()