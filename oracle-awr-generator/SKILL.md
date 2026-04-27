---
name: oracle-awr-generator
description: "Oracle AWR报告生成工具,用于连接Oracle数据库查询SNAP信息并生成AWR HTML报告。TRIGGER when: 用户提及AWR报告、Oracle巡检、数据库性能报告、生成AWR、Oracle性能分析等关键词时使用此技能。"
---

# Oracle AWR Report Generator

通过连接Oracle数据库,查询SNAP_ID范围,获取DBID和实例号,最终生成AWR HTML报告并保存到本地。

## ⚠️ 重要

- 不要预先检查脚本文件是否存在,直接执行。如果报错文件不存在,告知用户并结束流程。
- **【严禁】使用 cd 命令后再执行脚本**,必须直接使用脚本绝对路径执行。
- **【严禁】write临时python脚本再执行**,直接调用skill中已有的脚本即可。
- **必须严格按照流程顺序执行,禁止跳过或并行执行步骤**: 步骤1 → 步骤2 → 步骤3,每个步骤必须等待前一步骤完成后再执行。
- **密码中包含特殊字符时,必须使用单引号 `'...'` 包裹密码参数**。

## 脚本路径

脚本使用SKILL相对路径:
- `act_oracle_awr.py`: `/scripts/act_oracle_awr.py`
- `get_env_info.py`: `/scripts/get_env_info.py` — Oracle专用版本(只接受projectId一个参数,脚本内部固定hostAppName为"Oracle";与其他skill的同名脚本不同,不可混用)

## 依赖

需要 `oracledb` 库,未安装时先执行: `pip install oracledb`

## Workflow

### 步骤1: 解析数据库连接信息（⚠️ 此步骤可能需要停止,等待用户确认或补充信息）

从用户输入中解析Oracle数据库连接信息:
- **JDBC URL**: 如 `jdbc:oracle:thin:@//host:port/service_name`
- **用户名**: Oracle数据库用户名
- **密码**: Oracle数据库密码

**解析结果判断逻辑**:

#### 1.1 JDBC URL、用户名、密码均缺失

当用户未提供任何连接信息时,自动查询Oracle服务器信息:

1. 读取当前工作目录下的 `project.json` 文件,获取 `projectId` 字段
2. 调用 `get_env_info.py` 查询Oracle服务器信息,只需传入projectId参数(脚本内部固定hostAppName为"Oracle")

```bash
python3 /scripts/get_env_info.py "<projectId>"
```

**示例**:
```bash
python3 /scripts/get_env_info.py "PMP201908101518310"
```

**⚠️ 关键流程控制**: 查询完成后,**都必须立即停止当前流程**,展示查询结果给用户（**只展示jdbcUrl和userName字段,禁止展示pwd字段**）,等待用户确认或选择后,才能继续执行步骤1.3。

**返回结果处理**:

##### 1.1.1 project.json文件不存在
**立即终止流程**,返回告知用户:
```
当前目录下未找到project.json文件，请确认工作目录。
或请直接提供Oracle数据库连接信息:
- JDBC URL
- 用户名
- 密码
```
**流程结束,等待用户响应。**

##### 1.1.2 查询失败(返回数据为空)
**立即终止流程**,返回告知用户:
```
未查询到Oracle服务器信息,请联系管理员配置。
或请直接提供Oracle数据库连接信息:
- JDBC URL
- 用户名
- 密码
```
**流程结束,等待用户响应。**

##### 1.1.3 单个服务器信息
**立即停止流程**,展示服务器信息给用户(只展示jdbcUrl和userName,禁止展示pwd),格式:
```
找到Oracle数据库连接信息:
- JDBC URL: <jdbcUrl>
- 用户名: <userName>

请确认是否使用此连接信息？
```
**流程结束,等待用户确认。用户确认后,直接使用接口返回的jdbcUrl、userName、pwd连接数据库,继续执行步骤1.3。**

##### 1.1.4 多个服务器信息
**立即停止流程**,让用户选择(只展示jdbcUrl和userName,禁止展示pwd),格式:
```
找到多个Oracle数据库连接信息,请选择:
1. JDBC URL: <jdbcUrl> | 用户名: <userName>
2. JDBC URL: <jdbcUrl> | 用户名: <userName>
...
请输入您选择的序号。
```
**流程结束,等待用户选择。用户选择后,直接使用所选的jdbcUrl、userName、pwd连接数据库,继续执行步骤1.3。**

**注意**:
- 步骤1.1执行完毕后,**禁止继续执行步骤1.3或后续任何步骤**
- 必须等待用户明确回复(确认或选择)后,才能开始执行步骤1.3
- **绝对禁止在展示信息时泄露pwd字段**,pwd字段仅用于内部数据库连接
- pwd字段需要作为 `--password` 参数传给后续步骤的脚本命令

#### 1.2 JDBC URL、用户名、密码部分缺失

当三个字段中至少有一个有值但未全部提供时,**立即停止流程**,追问用户缺失的字段:

```
您提供的数据库连接信息不完整,请补充以下缺失字段:
- 缺失字段1: (如JDBC URL)
- 缺失字段2: (如密码)
...
```

**流程结束,等待用户补充信息。用户补充完整后,继续执行步骤1.3。**

#### 1.3 连接信息完整

当JDBC URL、用户名、密码三个字段均有值时,使用这些信息连接Oracle数据库,获取DBID和实例号:

```bash
python3 /scripts/act_oracle_awr.py --jdbc_url "<jdbc_url>" --username <username> --password '<password>' --command db_info
```

**示例**:
```bash
python3 /scripts/act_oracle_awr.py --jdbc_url "jdbc:oracle:thin:@//10.10.10.10:1521/cc" --username ccv81 --password 'smart' --command db_info
```

**返回结果处理**:

##### 1.3.1 连接失败
**立即终止流程**,返回告知用户:
```
Oracle数据库连接失败: <错误信息>
请检查JDBC URL、用户名和密码是否正确。
```
**流程结束,等待用户响应。**

##### 1.3.2 连接成功
记录返回的 `dbid`、`instance_number`、`instance_name`、`db_name` 信息,继续执行步骤2。

### 步骤2: 查询SNAP_ID范围（⚠️ 此步骤完成后必须停止,等待用户确认）

查询指定时间范围内的SNAP_ID信息,供用户选择生成AWR报告的时间区间:

```bash
python3 /scripts/act_oracle_awr.py --jdbc_url "<jdbc_url>" --username <username> --password '<password>' --command snap_ids --date_offset <日期偏移> --start_hour <开始小时> --end_hour <结束小时>
```

**参数说明**:
- `--date_offset`: 日期偏移量,1=昨天,0=今天,2=前天 (默认1,即昨天)
- `--start_hour`: SNAP开始小时 (可选,如14表示14:00)
- `--end_hour`: SNAP结束小时 (可选,如16表示16:00)

**如果用户未指定时间范围**,使用默认值: `--date_offset 1 --start_hour 14 --end_hour 16` (昨天14:00-16:00)

**示例**:
```bash
# 查询昨天14:00-16:00的SNAP_ID
python3 /scripts/act_oracle_awr.py --jdbc_url "jdbc:oracle:thin:@//10.10.10.10:1521/cc" --username ccv81 --password 'smart' --command snap_ids --date_offset 1 --start_hour 14 --end_hour 16

# 查询今天全天的SNAP_ID
python3 /scripts/act_oracle_awr.py --jdbc_url "jdbc:oracle:thin:@//10.10.10.10:1521/cc" --username ccv81 --password 'smart' --command snap_ids --date_offset 0
```

**⚠️ 关键流程控制**: 无论查询结果如何,**都必须立即停止当前流程**,展示SNAP信息给用户,等待用户确认选择SNAP_ID范围后,才能继续执行步骤3。

**返回结果处理**:

#### 2.1 无SNAP数据
**立即终止流程**,返回告知用户:
```
未找到指定时间范围内的SNAP_ID数据。
请确认:
1. 数据库是否在该时间段内有SNAPSHOT记录
2. 时间范围是否正确
3. 可以尝试不同的date_offset或时间范围
```
**流程结束,等待用户响应。**

#### 2.2 有SNAP数据
**立即停止流程**,展示所有SNAP信息给用户,格式:
```
数据库: <db_name>
实例: <instance_name>
DBID: <dbid>
实例号: <instance_number>

SNAP_ID范围: <min_snap_id> - <max_snap_id>
共 <snap_count> 个快照

快照列表:
| # | SNAP_ID | 开始时间 | 结束时间 |
|---|---------|---------|---------|
| 1 | <snap_id> | <begin_time> | <end_time> |
| 2 | <snap_id> | <begin_time> | <end_time> |
| ... | ... | ... | ... |

请回复选择的SNAP_ID(如选择单个SNAP_ID则自动取其与下一个快照作为区间;如需指定区间请回复如"82685-82687"):
```
**流程结束,等待用户选择。用户回复SNAP_ID后才能执行步骤3。**

**注意**:
- 步骤2执行完毕后,**禁止继续执行步骤3或后续任何步骤**
- 必须等待用户明确回复SNAP_ID后,才能开始执行步骤3
- 展示SNAP列表时,必须展示所有快照并加上序号(#),方便用户选择
- 用户只需回复一个SNAP_ID(如"82685"),则自动将该SNAP_ID作为begin_snap,下一个SNAP_ID作为end_snap
- 用户也可以回复区间格式(如"82685-82687"),则82685为begin_snap,82687为end_snap
- 用户也可以选择不指定小时范围,查询全天数据

### 步骤3: 生成AWR报告

使用用户确认的参数生成AWR HTML报告:

```bash
python3 /scripts/act_oracle_awr.py --jdbc_url "<jdbc_url>" --username <username> --password '<password>' --command generate_awr --dbid <dbid> --instance_number <instance_number> --begin_snap <用户选择的开始SNAP_ID> --end_snap <用户选择的结束SNAP_ID>
```

**示例**:
```bash
python3 /scripts/act_oracle_awr.py --jdbc_url "jdbc:oracle:thin:@//10.10.10.10:1521/cc" --username ccv81 --password 'smart' --command generate_awr --dbid 123456789 --instance_number 1 --begin_snap 100 --end_snap 105
```

**返回结果处理**:

#### 3.1 生成失败
返回告知用户:
```
AWR报告生成失败: <错误信息>
请检查参数是否正确。
```

#### 3.2 生成成功
**必须返回以下信息给用户**,特别强调HTML文件本地路径:

```
AWR报告已成功生成!

报告详情:
- DBID: <dbid>
- 实例号: <instance_number>
- SNAP范围: <begin_snap> - <end_snap>
- 报告行数: <line_count>
- 文件大小: <file_size> bytes

HTML报告本地路径: <local_path>

请使用浏览器打开以上路径的HTML文件查看完整AWR报告。
```

**⚠️ 关键要求**: 生成成功后,必须将 `local_path` 的值明确告知用户,这是步骤3的强制输出项,不可省略。

## 其他命令

### 仅获取DBID

```bash
python3 /scripts/act_oracle_awr.py --jdbc_url "<jdbc_url>" --username <username> --password '<password>' --command dbid
```

### 仅获取实例号

```bash
python3 /scripts/act_oracle_awr.py --jdbc_url "<jdbc_url>" --username <username> --password '<password>' --command instance_number
```

## 参考文件

| 文件 | 用途 |
|------|------|
| `references/OracleCreateAWR.json` | AWR生成SQL参考 |

## 完整示例

**场景1: 用户未提供连接信息(自动查询)**
```
用户: 帮我生成一个AWR报告
→ 步骤1: 解析用户输入 → JDBC URL、用户名、密码均缺失
→ 步骤1.1: 读取project.json获取projectId,查询Oracle服务器信息
  python3 /scripts/get_env_info.py "PMP201908101518310"
  查询到1个结果,输出:
找到Oracle数据库连接信息:
- JDBC URL: jdbc:oracle:thin:@//172.16.22.232:1521/cc
- 用户名: ccv81

请确认是否使用此连接信息？
→ [流程停止,等待用户确认]
用户: 确认

→ 步骤1.3: 使用接口返回的连接信息连接数据库
  python3 ... --jdbc_url "jdbc:oracle:thin:@//172.16.22.232:1521/cc" --username ccv81 --password 'smart' --command db_info
  结果: dbid=1234567890, instance_number=1, instance_name=cc, db_name=cc

→ 步骤2: 使用默认时间范围查询SNAP_ID
  [展示快照列表,等待用户回复SNAP_ID]
→ 步骤3: 用户回复SNAP_ID后,生成AWR报告,并返回HTML本地路径
```

**场景2: 用户未提供连接信息(查询到多个服务器)**
```
用户: 帮我生成AWR报告
→ 步骤1: 解析用户输入 → JDBC URL、用户名、密码均缺失
→ 步骤1.1: 读取project.json获取projectId,查询Oracle服务器信息
  python3 /scripts/get_env_info.py "PMP201908101518310"
  查询到2个结果,输出:
找到多个Oracle数据库连接信息,请选择:
1. JDBC URL: jdbc:oracle:thin:@//172.16.22.232:1521/cc | 用户名: ccv81
2. JDBC URL: jdbc:oracle:thin:@//10.10.10.10:1521/testdb | 用户名: system

请输入您选择的序号。
→ [流程停止,等待用户选择]
用户: 1

→ 步骤1.3: 使用选择的服务器信息连接数据库
→ 步骤2: 查询SNAP_ID [展示快照列表,等待用户回复SNAP_ID]
→ 步骤3: 生成AWR报告,返回HTML本地路径
```

**场景3: 用户部分提供连接信息**
```
用户: 用jdbc:oracle:thin:@//10.10.10.10:1521/testdb连接,生成AWR报告
→ 步骤1: 解析用户输入 → JDBC URL有值,用户名和密码缺失
→ 步骤1.2: 追问缺失字段
  输出:
您提供的数据库连接信息不完整,请补充以下缺失字段:
- 用户名
- 密码
→ [流程停止,等待用户补充]
用户: 账号admin密码admin123

→ 步骤1.3: 连接信息完整,连接数据库
  python3 ... --jdbc_url "jdbc:oracle:thin:@//10.10.10.10:1521/testdb" --username admin --password 'admin123' --command db_info
→ 步骤2: 查询SNAP_ID [展示快照列表,等待用户回复SNAP_ID]
→ 步骤3: 生成AWR报告,返回HTML本地路径
```

**场景4: 用户完整提供连接信息**
```
用户: 用jdbc:oracle:thin:@//10.10.10.10:1521/testdb连接,账号admin密码admin123,生成昨天的AWR报告
→ 步骤1: 解析用户输入 → JDBC URL、用户名、密码均有值
→ 步骤1.3: 直接连接数据库
  python3 ... --jdbc_url "jdbc:oracle:thin:@//10.10.10.10:1521/testdb" --username admin --password 'admin123' --command db_info
→ 步骤2: 查询昨天的SNAP_ID (不指定小时范围,查询全天)
  python3 ... --jdbc_url "jdbc:oracle:thin:@//10.10.10.10:1521/testdb" --username admin --password 'admin123' --command snap_ids --date_offset 1
  [展示快照列表,等待用户回复SNAP_ID]
→ 步骤3: 生成AWR报告,返回HTML本地路径
```

**场景5: 连接失败**
```
用户: 帮我生成AWR报告
→ 步骤1: 查询到服务器信息,用户确认后连接
→ 步骤1.3: 连接数据库失败
  结果: Oracle数据库连接失败: ORA-01017: invalid username/password; logon denied
  输出:
Oracle数据库连接失败: ORA-01017: invalid username/password; logon denied
请检查JDBC URL、用户名和密码是否正确。
→ [流程终止,等待用户响应]
```

**场景6: project.json不存在**
```
用户: 帮我生成AWR报告
→ 步骤1: 解析用户输入 → JDBC URL、用户名、密码均缺失
→ 步骤1.1: 读取project.json → 文件不存在
  输出:
当前目录下未找到project.json文件，请确认工作目录。
或请直接提供Oracle数据库连接信息:
- JDBC URL
- 用户名
- 密码
→ [流程终止,等待用户响应]
```

**场景7: 查询不到Oracle服务器信息**
```
用户: 帮我生成AWR报告
→ 步骤1: 解析用户输入 → JDBC URL、用户名、密码均缺失
→ 步骤1.1: 读取project.json获取projectId,查询Oracle服务器信息
  python3 /scripts/get_env_info.py "PMP201908101518310"
  结果: 返回空列表
  输出:
未查询到Oracle服务器信息,请联系管理员配置。
或请直接提供Oracle数据库连接信息:
- JDBC URL
- 用户名
- 密码
→ [流程终止,等待用户响应]
```

## 注意事项

- 需要 `oracledb` 库,未安装时先执行 `pip install oracledb`
- AWR报告格式为HTML,需用浏览器打开查看
- 生成AWR报告需要DBA权限或对 `dbms_workload_repository` 包的执行权限
- **密码中包含特殊字符（如 $、%、! 等）的处理**:
  - **必须使用单引号 `'...'` 包裹密码参数**
  - 单引号内的 `$` 不会被bash解析为变量引用
  - **【严禁】使用双引号包裹密码参数**,会导致 `$` 被解析为变量
- AWR报告默认保存到当前工作目录下的 `downloads` 目录
- 报告文件命名格式: `awr_report_<dbid>_<instance_number>_<begin_snap>_<end_snap>_<timestamp>.html`