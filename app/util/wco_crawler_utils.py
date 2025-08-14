import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_fixed

from app.core.config import settings
from app.model.wco_hs_model import WcoHsSection, WcoHsChapter, WcoHsHeading

common_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/90.0.4430.93 Safari/537.36"
}

main_url = settings.WCO_HSCODE_MAIN_URL


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))  # 重试3次，每次间隔2秒
async def fetch_page(url, is_ajax):
    headers = common_headers.copy()
    if is_ajax:
        headers.update({"X-Requested-With": "XMLHttpRequest"})
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # 请求失败则抛出异常
    return response.text


async def get_newest_version(html):
    """获取当前最新版本"""
    soup = BeautifulSoup(html, "html.parser")
    select = soup.find("select", id="filter-edition")
    first_option = select.find("option")
    version = first_option.get_text()
    return version


async def get_code_and_title(html, class_name, code_prefix="", process_code=False):
    soup = BeautifulSoup(html, "html.parser")
    # 查找所有class中包含class_name的div标签
    divs = soup.find_all("div", class_=class_name)
    results = []
    for div in divs:
        # 提取data-list-url属性
        list_url = div.get("data-list-url")
        # 提取title
        title_tag = div.find("h2", id=lambda x: x and x.startswith("hs-code:"))
        title = title_tag.get_text(strip=True).replace('\xa0', '') if title_tag else ""
        # 提取code
        if process_code:
            code_tags = div.find("span", class_="section-number")
            code = code_tags.get_text(strip=True) if code_tags else ""
            code = code[len(code_prefix):].replace(".", "")
        else:
            code = title_tag.get("id", "").split(":")[1]
        # 其他子节点数据也可以按需提取
        results.append({
            "list_url": list_url,
            "code": code,
            "title": title
        })
    return results


async def get_section(version):
    section_url = main_url + "/en/harmonized-system/" + version + "/en"
    html = await fetch_page(section_url, False)
    section_list = await get_code_and_title(html, "section-item")
    return section_list


async def get_chapter(section: WcoHsSection):
    chapter_url = main_url + section.load_children_url + "?_wrapper_format=ajax"
    chapter_html = await fetch_page(chapter_url, True)
    chapter_list = await get_code_and_title(chapter_html, "chapter-item", "Chapter ", True)
    if not chapter_list:
        print("No Chapter Found Under %s", section.section_code)
    return chapter_list


async def get_heading(chapter:WcoHsChapter):
    heading_url = main_url + chapter.load_children_url + "?_wrapper_format=ajax"
    heading_html = await fetch_page(heading_url, True)
    heading_list = await get_code_and_title(heading_html, "heading-item", "Heading ",True)
    if not heading_list:
        print("No Heading Found Under %s", chapter.chapter_code)
    return heading_list


async def get_subheading(heading:WcoHsHeading):
    if heading.load_children_url:
        subheading_url = main_url + heading.load_children_url + "?_wrapper_format=ajax"
        subheading_html = await fetch_page(subheading_url, True)
        subheading_list = await get_code_and_title(subheading_html, "subheading-item", "",True)
        if not subheading_list:
            print("No HSCode Found Under %s", heading.heading_code)
        return subheading_list
    return None


def main():
    import asyncio
    headings = asyncio.run(get_subheading(WcoHsHeading(heading_code="3301", load_children_url="/en/harmonized-system/default/308996/en/94561")))
    for heading in headings:
        print(heading["code"])

if __name__ == "__main__":
    main()