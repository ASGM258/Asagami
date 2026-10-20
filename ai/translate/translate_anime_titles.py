"""
动漫名称、简介和体裁翻译脚本
功能：将数据库中的动漫英文名称翻译成中文并更新到原表
数据库：MySQL (localhost:3306)
AI服务：DeepSeek API
支持翻译字段：
  - anime表：title（标题）、synopsis（简介）、genres（体裁）
  - anime_character表：name（角色名）、about（简介）、nicknames（昵称）
"""

import mysql.connector
from mysql.connector import Error
import requests
import json
import os
import time


# 配置信息
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', '3306')),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'backend_asagami'),
}

# ⚠️ 密钥只从环境变量读取，不要写进源码（本文件会被提交到仓库）
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_API_URL = os.environ.get(
    'DEEPSEEK_API_URL', 'https://api.deepseek.com/v1/chat/completions'
)

if not DEEPSEEK_API_KEY:
    raise SystemExit(
        "缺少 DEEPSEEK_API_KEY：请先设置环境变量后再运行，例如\n"
        "  PowerShell: $env:DEEPSEEK_API_KEY='sk-xxx'; python translate_anime_titles.py"
    )


def get_db_connection():
    """建立数据库连接"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            print("✓ 成功连接到MySQL数据库")
            return connection
    except Error as e:
        print(f" 连接数据库失败: {e}")
        return None


def translate_with_deepseek(text, mode='title', field_type='title'):
    """使用DeepSeek API进行翻译
    
    Args:
        text: 需要翻译的文本
        mode: 翻译模式，'title'为标题翻译，'synopsis'为简介翻译，'genres'为体裁翻译
              'character_name'为角色名翻译，'character_about'为角色简介翻译，'character_nicknames'为角色昵称翻译
        field_type: 字段类型标识，用于区分不同的翻译场景
    """
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}'
    }
    
    if mode == 'title':
        prompt = f"""请将以下动漫名称翻译成准确的中文译名。要求：
1. 只返回翻译结果，不要有任何解释或额外文字
2. 如果已经是中文，保持原样
3. 如果是知名动漫，使用官方或广泛认可的中文译名
4. 保留原有的标点符号和特殊字符

需要翻译的名称：{text}"""
    elif mode == 'synopsis':
        prompt = f"""请将以下动漫简介翻译成流畅自然的中文。要求：
1. 保持原文的意思和情感色彩
2. 使用通顺、地道的中文表达
3. 专有名词（人名、地名等）保留原文或使用公认的中文译名
4. 保持段落结构和标点符号
5. 只返回翻译结果，不要有任何解释或额外文字

需要翻译的简介：{text}"""
    elif mode == 'genres':
        prompt = f"""请将以下动漫体裁标签翻译成中文。要求：
1. 每个标签用逗号分隔，保持原有顺序
2. 使用常见的中文体裁术语（如：动作、冒险、科幻、奇幻、悬疑、喜剧、剧情等）
3. 只返回翻译结果，不要有任何解释或额外文字
4. 保留逗号分隔符

需要翻译的体裁标签：{text}"""
    elif mode == 'character_name':
        prompt = f"""请将以下动漫角色名称翻译成准确的中文译名。要求：
1. 只返回翻译结果，不要有任何解释或额外文字
2. 如果已经是中文，保持原样
3. 如果是知名角色，使用官方或广泛认可的中文译名
4. 保留原有的标点符号和特殊字符

需要翻译的角色名：{text}"""
    elif mode == 'character_about':
        prompt = f"""请将以下动漫角色简介翻译成流畅自然的中文。要求：
1. 保持原文的意思和情感色彩
2. 使用通顺、地道的中文表达
3. 专有名词（人名、地名等）保留原文或使用公认的中文译名
4. 保持段落结构和标点符号
5. 只返回翻译结果，不要有任何解释或额外文字

需要翻译的角色简介：{text}"""
    elif mode == 'character_nicknames':
        prompt = f"""请将以下动漫角色昵称/别名翻译成中文。要求：
1. 每个昵称用逗号分隔，保持原有顺序
2. 使用符合角色特征的中文昵称
3. 只返回翻译结果，不要有任何解释或额外文字
4. 保留逗号分隔符

需要翻译的昵称：{text}"""
    
    # 根据翻译模式设置不同的参数
    if mode in ['synopsis', 'character_about']:
        # 简介翻译需要更多token
        max_tokens = 8000
        system_prompt = '你是一个专业的动漫简介翻译助手，擅长将长篇英文简介准确、流畅地翻译成中文。'
    elif mode in ['character_nicknames']:
        # 昵称翻译使用中等token
        max_tokens = 500
        system_prompt = '你是一个专业的动漫角色昵称翻译助手，擅长将各种语言的昵称准确翻译成中文。'
    else:
        # 标题、体裁、角色名翻译使用较少token
        max_tokens = 200
        system_prompt = '你是一个专业的动漫名称翻译助手，擅长将各种语言的动漫名称准确翻译成中文。'
    
    data = {
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.3,
        'max_tokens': max_tokens
    }
    
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=60)
        response.raise_for_status()
            
        result = response.json()
        translated_text = result['choices'][0]['message']['content'].strip()
            
        # 检查是否被截断
        finish_reason = result['choices'][0].get('finish_reason', '')
        if finish_reason == 'length':
            print(f"\n⚠️ 警告: API返回被截断 (max_tokens={max_tokens})")
            
        # 清理可能的引号或多余空格
        translated_text = translated_text.strip('\"\'').strip()
            
        return translated_text
    except Exception as e:
        print(f"✗ API调用失败: {e}")
        return None


def get_anime_list(connection, field='title', table='anime'):
    """获取所有需要翻译的记录列表
    
    Args:
        connection: 数据库连接
        field: 要翻译的字段
        table: 表名，'anime'或'anime_character'
    """
    cursor = connection.cursor(dictionary=True)
    
    # 查询所有指定字段不为空且不是中文的记录
    query = f"""
        SELECT id, {field}
        FROM {table}
        WHERE {field} IS NOT NULL AND {field} != ''
        ORDER BY id
    """
    
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    
    return results


def update_field(connection, record_id, new_value, field='title', table='anime'):
    """更新记录字段值
    
    Args:
        connection: 数据库连接
        record_id: 记录ID
        new_value: 新的字段值
        field: 要更新的字段名
        table: 表名，'anime'或'anime_character'
    """
    cursor = connection.cursor()
    
    query = f"UPDATE {table} SET {field} = %s WHERE id = %s"
    cursor.execute(query, (new_value, record_id))
    connection.commit()
    
    cursor.close()
    return True


def is_chinese(text):
    """检查文本是否包含中文字符"""
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False


def main():
    """主函数"""
    print("=" * 60)
    print("动漫名称和简介翻译工具")
    print("=" * 60)
    
    # 选择翻译模式
    print("\n请选择翻译模式：")
    print("1. 翻译动漫标题 (title)")
    print("2. 翻译动漫简介 (synopsis)")
    print("3. 翻译动漫体裁 (genres)")
    print("4. 翻译角色名称 (name)")
    print("5. 翻译角色简介 (about)")
    print("6. 翻译角色昵称 (nicknames)")
    choice = input("请输入选项 (1-6): ").strip()
    
    if choice == '1':
        field = 'title'
        field_name = '标题'
        translate_mode = 'title'
        table = 'anime'
    elif choice == '2':
        field = 'synopsis'
        field_name = '简介'
        translate_mode = 'synopsis'
        table = 'anime'
    elif choice == '3':
        field = 'genres'
        field_name = '体裁'
        translate_mode = 'genres'
        table = 'anime'
    elif choice == '4':
        field = 'name'
        field_name = '角色名称'
        translate_mode = 'character_name'
        table = 'anime_character'
    elif choice == '5':
        field = 'about'
        field_name = '角色简介'
        translate_mode = 'character_about'
        table = 'anime_character'
    elif choice == '6':
        field = 'nicknames'
        field_name = '角色昵称'
        translate_mode = 'character_nicknames'
        table = 'anime_character'
    else:
        print("无效选项，默认翻译标题")
        field = 'title'
        field_name = '标题'
        translate_mode = 'title'
        table = 'anime'
    
    # 连接数据库
    connection = get_db_connection()
    if not connection:
        return
    
    try:
        # 获取记录列表
        print(f"\n正在获取需要翻译的{field_name}...")
        record_list = get_anime_list(connection, field=field, table=table)
        total_count = len(record_list)
        print(f"共找到 {total_count} 条记录\n")
        
        # 处理每条记录
        success_count = 0
        skip_count = 0
        fail_count = 0
        
        for index, record in enumerate(record_list, 1):
            record_id = record['id']
            original_text = record[field]
            
            # 如果字段值为NULL，跳过
            if original_text is None:
                print(f"[{index}/{total_count}] ID: {record_id} | ⚠ 字段值为NULL，跳过\n")
                skip_count += 1
                continue
            
            # 截断显示长度
            display_text = original_text[:50] + '...' if len(original_text) > 50 else original_text
            print(f"[{index}/{total_count}] ID: {record_id} | 原文本: {display_text}")
            
            # 如果已经是中文，跳过
            if is_chinese(original_text):
                print(f"  ⚠ 已是中文，跳过\n")
                skip_count += 1
                continue
            
            # 调用API翻译
            print(f"  → 正在翻译...", end=' ')
            translated_text = translate_with_deepseek(original_text, mode=translate_mode)
            
            if translated_text:
                # 显示翻译结果的长度信息
                original_len = len(original_text)
                translated_len = len(translated_text)
                display_translated = translated_text[:80] + '...' if len(translated_text) > 80 else translated_text
                print(f"\n  ✓ 翻译结果 ({translated_len}字): {display_translated}")
                
                # 更新数据库
                if update_field(connection, record_id, translated_text, field=field, table=table):
                    print(f"  ✓ 更新成功\n")
                    success_count += 1
                else:
                    print(f"  ✗ 更新失败\n")
                    fail_count += 1
            else:
                print(f"   翻译失败\n")
                fail_count += 1
            
            # 避免请求过快，添加延迟
            time.sleep(1)
        
        # 统计结果
        print("\n" + "=" * 60)
        print(f"{field_name}翻译完成！统计信息：")
        print(f"  总记录数: {total_count}")
        print(f"  成功翻译: {success_count}")
        print(f"  跳过(已中文或NULL): {skip_count}")
        print(f"  失败: {fail_count}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if connection.is_connected():
            connection.close()
            print("\n数据库连接已关闭")


if __name__ == '__main__':
    main()
