#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Oracle AWR报告生成工具 - 连接Oracle数据库,查询SNAP信息并生成AWR报告

使用方式: 通过命令行参数调用,支持查询SNAP_ID、获取DBID/实例号、生成AWR报告等功能

依赖: oracledb (python-oracledb库)
    安装: pip install oracledb

用法:
    python3 act_oracle_awr.py --jdbc_url <jdbc_url> --username <username> --password <password> --command <command> [其他参数]

示例:
    # 查询SNAP_ID范围
    python3 act_oracle_awr.py --jdbc_url "jdbc:oracle:thin:@//172.16.22.232:1521/cc" --username ccv81 --password 'smart' --command snap_ids --date_offset 1 --start_hour 14 --end_hour 16

    # 获取DBID
    python3 act_oracle_awr.py --jdbc_url "jdbc:oracle:thin:@//172.16.22.232:1521/cc" --username ccv81 --password 'smart' --command dbid

    # 获取实例号
    python3 act_oracle_awr.py --jdbc_url "jdbc:oracle:thin:@//172.16.22.232:1521/cc" --username ccv81 --password 'smart' --command instance_number

    # 生成AWR报告
    python3 act_oracle_awr.py --jdbc_url "jdbc:oracle:thin:@//172.16.22.232:1521/cc" --username ccv81 --password 'smart' --command generate_awr --dbid <dbid> --instance_number <instance_number> --begin_snap <begin_snap_id> --end_snap <end_snap_id>

注意:
    - AWR报告会保存到当前工作目录下的downloads目录
    - 报告格式为HTML
"""

import argparse
import json
import sys
import os
import re
from datetime import datetime


def parse_jdbc_url(jdbc_url: str) -> dict:
    """
    解析Oracle JDBC URL,提取host、port、service_name

    支持的格式:
    - jdbc:oracle:thin:@//host:port/service_name  (Easy Connect Plus)
    - jdbc:oracle:thin:@host:port:SID              (SID格式)
    - jdbc:oracle:thin:@host:port/service_name      (Service格式)
    - jdbc:oracle:thin:@(description=...)           (TNS格式)

    Returns:
        dict: 包含host, port, service_name/sid的字典
    """
    # 去掉jdbc:oracle:thin:@前缀
    url_body = jdbc_url.replace('jdbc:oracle:thin:@', '')

    # Easy Connect Plus格式: //host:port/service_name
    if url_body.startswith('//'):
        match = re.match(r'//([^:/]+):(\d+)/(.+)', url_body)
        if match:
            return {
                'host': match.group(1),
                'port': int(match.group(2)),
                'service_name': match.group(3)
            }

    # SID格式: host:port:SID
    match_sid = re.match(r'([^:/]+):(\d+):(.+)', url_body)
    if match_sid:
        return {
            'host': match_sid.group(1),
            'port': int(match_sid.group(2)),
            'sid': match_sid.group(3)
        }

    # Service格式: host:port/service_name
    match_svc = re.match(r'([^:/]+):(\d+)/(.+)', url_body)
    if match_svc:
        return {
            'host': match_svc.group(1),
            'port': int(match_svc.group(2)),
            'service_name': match_svc.group(3)
        }

    return {'status': 'error', 'message': f'无法解析JDBC URL: {jdbc_url}'}


def connect_oracle(jdbc_url: str, username: str, password: str):
    """
    连接Oracle数据库

    Args:
        jdbc_url: JDBC URL字符串
        username: 数据库用户名
        password: 数据库密码

    Returns:
        oracledb.Connection对象 或 None(失败时)
    """
    try:
        import oracledb
    except ImportError:
        print(json.dumps({
            'status': 'error',
            'message': 'oracledb库未安装,请先执行: pip install oracledb'
        }, ensure_ascii=False))
        sys.exit(1)

    conn_params = parse_jdbc_url(jdbc_url)
    if 'status' in conn_params and conn_params['status'] == 'error':
        return None, conn_params

    host = conn_params.get('host')
    port = conn_params.get('port', 1521)
    service_name = conn_params.get('service_name')
    sid = conn_params.get('sid')

    try:
        if service_name:
            conn = oracledb.connect(
                user=username,
                password=password,
                host=host,
                port=port,
                service_name=service_name
            )
        elif sid:
            conn = oracledb.connect(
                user=username,
                password=password,
                host=host,
                port=port,
                sid=sid
            )
        else:
            return None, {'status': 'error', 'message': 'JDBC URL中未找到service_name或sid'}

        return conn, {'status': 'success', 'message': f'成功连接到 {host}:{port}'}
    except oracledb.Error as e:
        error_obj, = e.args
        return None, {
            'status': 'error',
            'message': f'Oracle连接失败: {error_obj.message}',
            'error_code': error_obj.code
        }
    except Exception as e:
        return None, {'status': 'error', 'message': f'连接失败: {str(e)}'}


def query_snap_ids(conn, date_offset: int = 1, start_hour: int = None, end_hour: int = None) -> dict:
    """
    查询指定日期范围的SNAP_ID最小值和最大值

    Args:
        conn: Oracle连接对象
        date_offset: 日期偏移量(相对于今天,1表示昨天)
        start_hour: 开始小时(可选,如14表示14:00)
        end_hour: 结束小时(可选,如16表示16:00)

    Returns:
        dict: 包含min_snap_id, max_snap_id, snap_count, snap_time_range的结果字典
    """
    try:
        cursor = conn.cursor()

        # 构建SQL查询
        sql = """
            SELECT MIN(snap_id), MAX(snap_id), COUNT(*),
                   MIN(begin_interval_time), MAX(end_interval_time)
            FROM dba_hist_snapshot
            WHERE TRUNC(end_interval_time) = TRUNC(SYSDATE - :date_offset)
        """

        params = {'date_offset': date_offset}

        if start_hour is not None and end_hour is not None:
            sql += " AND TO_CHAR(end_interval_time, 'HH24') BETWEEN :start_hour AND :end_hour"
            params['start_hour'] = str(start_hour)
            params['end_hour'] = str(end_hour)

        cursor.execute(sql, params)
        row = cursor.fetchone()

        if row and row[0] is not None:
            min_snap, max_snap, count, min_time, max_time = row

            # 获取详细的SNAP_ID列表供用户选择
            detail_sql = """
                SELECT snap_id, TO_CHAR(begin_interval_time, 'YYYY-MM-DD HH24:MI:SS'),
                       TO_CHAR(end_interval_time, 'YYYY-MM-DD HH24:MI:SS')
                FROM dba_hist_snapshot
                WHERE TRUNC(end_interval_time) = TRUNC(SYSDATE - :date_offset)
            """
            detail_params = {'date_offset': date_offset}
            if start_hour is not None and end_hour is not None:
                detail_sql += " AND TO_CHAR(end_interval_time, 'HH24') BETWEEN :start_hour AND :end_hour"
                detail_params['start_hour'] = str(start_hour)
                detail_params['end_hour'] = str(end_hour)
            detail_sql += " ORDER BY snap_id"

            cursor.execute(detail_sql, detail_params)
            snap_list = []
            for snap_row in cursor.fetchall():
                snap_list.append({
                    'snap_id': snap_row[0],
                    'begin_time': snap_row[1],
                    'end_time': snap_row[2]
                })

            cursor.close()

            return {
                'status': 'success',
                'min_snap_id': min_snap,
                'max_snap_id': max_snap,
                'snap_count': count,
                'begin_time': str(min_time) if min_time else '',
                'end_time': str(max_time) if max_time else '',
                'snap_list': snap_list
            }
        else:
            cursor.close()
            return {
                'status': 'error',
                'message': f'未找到日期偏移{date_offset}天{(f" {start_hour}:00-{end_hour}:00" if start_hour else "")}范围内的SNAP_ID数据'
            }
    except Exception as e:
        return {'status': 'error', 'message': f'查询SNAP_ID失败: {str(e)}'}


def query_dbid(conn) -> dict:
    """
    获取数据库DBID

    Args:
        conn: Oracle连接对象

    Returns:
        dict: 包含dbid的结果字典
    """
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT dbid FROM v$database")
        row = cursor.fetchone()
        cursor.close()
        if row:
            return {'status': 'success', 'dbid': row[0]}
        else:
            return {'status': 'error', 'message': '无法获取DBID'}
    except Exception as e:
        return {'status': 'error', 'message': f'查询DBID失败: {str(e)}'}


def query_instance_number(conn) -> dict:
    """
    获取实例号

    Args:
        conn: Oracle连接对象

    Returns:
        dict: 包含instance_number和instance_name的结果字典
    """
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT instance_number, instance_name FROM v$instance")
        row = cursor.fetchone()
        cursor.close()
        if row:
            return {
                'status': 'success',
                'instance_number': row[0],
                'instance_name': row[1]
            }
        else:
            return {'status': 'error', 'message': '无法获取实例号'}
    except Exception as e:
        return {'status': 'error', 'message': f'查询实例号失败: {str(e)}'}


def generate_awr_report(conn, dbid: int, instance_number: int, begin_snap: int, end_snap: int) -> dict:
    """
    生成AWR HTML报告并保存到本地文件

    Args:
        conn: Oracle连接对象
        dbid: 数据库DBID
        instance_number: 实例号
        begin_snap: 开始SNAP_ID
        end_snap: 结束SNAP_ID

    Returns:
        dict: 包含报告文件路径的结果字典
    """
    try:
        cursor = conn.cursor()

        # 调用dbms_workload_repository.awr_report_html生成AWR报告
        # 使用SELECT output FROM TABLE()方式获取报告内容
        sql = """
            SELECT output FROM TABLE(dbms_workload_repository.awr_report_html(:dbid, :instance_number, :begin_snap, :end_snap))
        """

        cursor.execute(sql, {
            'dbid': dbid,
            'instance_number': instance_number,
            'begin_snap': begin_snap,
            'end_snap': end_snap
        })

        # 收集所有output行
        report_lines = []
        for row in cursor.fetchall():
            if row[0]:
                report_lines.append(row[0])

        cursor.close()

        if not report_lines:
            return {'status': 'error', 'message': 'AWR报告生成失败: 无输出内容'}

        # 拼接报告内容
        report_content = '\n'.join(report_lines)

        # 确定下载目录
        downloads_dir = os.path.join(os.getcwd(), 'downloads')
        os.makedirs(downloads_dir, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'awr_report_{dbid}_{instance_number}_{begin_snap}_{end_snap}_{timestamp}.html'
        local_path = os.path.join(downloads_dir, filename)

        # 写入文件
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

        file_size = os.path.getsize(local_path)

        return {
            'status': 'success',
            'message': f'AWR报告已生成并保存到本地: {local_path}',
            'local_path': local_path,
            'file_size': file_size,
            'dbid': dbid,
            'instance_number': instance_number,
            'begin_snap': begin_snap,
            'end_snap': end_snap,
            'line_count': len(report_lines)
        }
    except Exception as e:
        return {'status': 'error', 'message': f'生成AWR报告失败: {str(e)}'}


def get_db_info(conn) -> dict:
    """
    获取数据库基本信息(DBID + 实例号 + 实例名),一步到位

    Args:
        conn: Oracle连接对象

    Returns:
        dict: 包含dbid, instance_number, instance_name的结果字典
    """
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.dbid, i.instance_number, i.instance_name, d.name
            FROM v$database d, v$instance i
        """)
        row = cursor.fetchone()
        cursor.close()
        if row:
            return {
                'status': 'success',
                'dbid': row[0],
                'instance_number': row[1],
                'instance_name': row[2],
                'db_name': row[3]
            }
        else:
            return {'status': 'error', 'message': '无法获取数据库信息'}
    except Exception as e:
        return {'status': 'error', 'message': f'查询数据库信息失败: {str(e)}'}


def main():
    parser = argparse.ArgumentParser(description='Oracle AWR报告生成工具')

    # 连接参数
    parser.add_argument('--jdbc_url', required=True,
                        help='Oracle JDBC URL (如: jdbc:oracle:thin:@//172.16.22.232:1521/cc)')
    parser.add_argument('--username', required=True, help='数据库用户名')
    parser.add_argument('--password', required=True, help='数据库密码')

    # 命令参数
    parser.add_argument('--command', required=True,
                        choices=['snap_ids', 'dbid', 'instance_number', 'db_info', 'generate_awr'],
                        help='执行的命令: snap_ids(查询SNAP范围)/dbid(获取DBID)/instance_number(获取实例号)/db_info(获取DBID+实例号)/generate_awr(生成AWR报告)')

    # SNAP_ID查询参数
    parser.add_argument('--date_offset', type=int, default=1,
                        help='日期偏移量(相对于今天,1=昨天,0=今天,默认1)')
    parser.add_argument('--start_hour', type=int, default=None,
                        help='SNAP开始小时(如14表示14:00,可选)')
    parser.add_argument('--end_hour', type=int, default=None,
                        help='SNAP结束小时(如16表示16:00,可选)')

    # AWR生成参数
    parser.add_argument('--dbid', type=int, default=None, help='数据库DBID (用于generate_awr)')
    parser.add_argument('--instance_number', type=int, default=None, help='实例号 (用于generate_awr)')
    parser.add_argument('--begin_snap', type=int, default=None, help='开始SNAP_ID (用于generate_awr)')
    parser.add_argument('--end_snap', type=int, default=None, help='结束SNAP_ID (用于generate_awr)')

    args = parser.parse_args()

    # 连接数据库
    conn, conn_result = connect_oracle(args.jdbc_url, args.username, args.password)

    if conn is None:
        print(json.dumps(conn_result, indent=2, ensure_ascii=False))
        sys.exit(1)

    # 执行命令
    try:
        if args.command == 'snap_ids':
            result = query_snap_ids(conn, args.date_offset, args.start_hour, args.end_hour)

        elif args.command == 'dbid':
            result = query_dbid(conn)

        elif args.command == 'instance_number':
            result = query_instance_number(conn)

        elif args.command == 'db_info':
            result = get_db_info(conn)

        elif args.command == 'generate_awr':
            # 校验必要参数
            if args.dbid is None:
                result = {'status': 'error', 'message': 'generate_awr命令需要--dbid参数'}
            elif args.instance_number is None:
                result = {'status': 'error', 'message': 'generate_awr命令需要--instance_number参数'}
            elif args.begin_snap is None:
                result = {'status': 'error', 'message': 'generate_awr命令需要--begin_snap参数'}
            elif args.end_snap is None:
                result = {'status': 'error', 'message': 'generate_awr命令需要--end_snap参数'}
            else:
                result = generate_awr_report(conn, args.dbid, args.instance_number, args.begin_snap, args.end_snap)

        else:
            result = {'status': 'error', 'message': f'未知命令: {args.command}'}

    except Exception as e:
        result = {'status': 'error', 'message': f'执行失败: {str(e)}'}

    finally:
        conn.close()

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result.get('status') == 'error':
        sys.exit(1)


if __name__ == '__main__':
    main()