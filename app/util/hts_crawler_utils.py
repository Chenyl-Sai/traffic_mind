import requests
import os
import json

from app.core.config import settings
from app.schema.hts import HtsRecord


# ?from=0101.&to=9999.&format=JSON&styles=false
async def get_current_release():
    response = requests.get(settings.HTS_CURRENT_RELEASE_URL)
    # {
    #     "name": "2025HTSRev16",
    #     "description": "2025 HTS Revision 16",
    #     "title": "Revision 16 (2025)"
    # }
    return response.json()

async def download_file_to_cache(url: str, filename: str):
    """
    下载文件到/download文件夹下并缓存

    Args:
        url: 文件下载地址
        filename: 保存的文件名

    Returns:
        str: 文件保存的完整路径
    """
    # 创建download文件夹（如果不存在）
    print(os.path.expanduser("~"))
    download_dir = os.path.join(os.path.expanduser("~"), ".traffic_mind/cache")
    os.makedirs(download_dir, exist_ok=True)

    # 构造文件完整路径
    file_path = os.path.join(download_dir, filename)

    # 检查文件是否已存在
    if os.path.exists(file_path):
        return file_path

    # 下载文件
    response = requests.get(url)
    response.raise_for_status()  # 确保请求成功

    # 保存文件
    with open(file_path, 'wb') as f:
        f.write(response.content)

    return file_path

async def read_json_file_to_objects(file_path: str, model_class) -> list:
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    # 如果数据是列表，逐个转换为模型对象
    if isinstance(data, list):
        return [model_class(**item) for item in data]
    # 如果是单个对象，包装成列表
    elif isinstance(data, dict):
        return [model_class(**data)]
    else:
        raise ValueError("JSON数据格式不正确，应为对象或对象列表")

async def read_data(current_release_name: str) -> list[HtsRecord]:
    url = settings.HTS_EXPORT_CURRENT_JSON_URL + "?from=0101.&to=9999.&format=JSON&styles=false"
    file_path = await download_file_to_cache(url, current_release_name + ".json")
    return await read_json_file_to_objects(file_path, HtsRecord)