"""论文处理器：提取论文结构化信息"""

from dataclasses import dataclass, field
from typing import List
import re
from loguru import logger


@dataclass
class PaperInfo:
    """论文信息数据类"""

    title: str
    abstract: str
    sections: List[dict]  # [{"title": "Intro", "content": "..."}]
    references: List[str] = field(default_factory=list)
    raw_text: str = ""


class PaperProcessor:
    """论文处理器，提取论文结构化信息"""

    def extract_title(self, text: str) -> str:
        """提取论文标题（取第一行非空行）"""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        return lines[0] if lines else "未知标题"

    def extract_abstract(self, text: str) -> str:
        """提取摘要"""
        patterns = [
            r"(?:Abstract|ABSTRACT|摘要)\s*[:：]?\s*\n?(.*?)(?=\n\s*(?:Introduction|INTRODUCTION|1\.|1\s|引言))",
            r"(?:Abstract|ABSTRACT|摘要)\s*[:：]?\s*\n?(.*?)(?=\n\s*(?:Keywords|关键词))",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return ""

    def extract_sections(self, text: str) -> List[dict]:
        """提取论文章节"""
        # 匹配数字编号的章节标题
        section_pattern = r'\n(\d+\.?\s+[A-Z][^\n]+)\n'
        matches = list(re.finditer(section_pattern, text))

        sections = []
        for i, match in enumerate(matches):
            title = match.group(1).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            sections.append({"title": title, "content": content})

        # 如果没有找到编号章节，尝试按常见标题分割
        if not sections:
            common_headers = [
                "Introduction",
                "Method",
                "Results",
                "Discussion",
                "Conclusion",
                "References",
            ]
            for header in common_headers:
                pattern = rf'\n({header})\s*\n'
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    start = match.end()
                    end = len(text)
                    for next_header in common_headers:
                        next_match = re.search(
                            rf'\n({next_header})\s*\n', text[start:], re.IGNORECASE
                        )
                        if next_match and next_match.start() > 0:
                            end = start + next_match.start()
                            break
                    sections.append(
                        {"title": match.group(1), "content": text[start:end].strip()}
                    )

        logger.info(f"提取到 {len(sections)} 个章节")
        return sections

    def extract_references(self, text: str) -> List[str]:
        """提取参考文献"""
        ref_pattern = r'(?:References|REFERENCES|参考文献)\s*\n(.*?)(?:\Z)'
        match = re.search(ref_pattern, text, re.DOTALL)

        if not match:
            return []

        ref_text = match.group(1)
        refs = []
        for line in ref_text.split("\n"):
            line = line.strip()
            if line and len(line) > 10:
                refs.append(line)

        logger.info(f"提取到 {len(refs)} 条参考文献")
        return refs

    def process(self, text: str) -> PaperInfo:
        """完整处理论文"""
        title = self.extract_title(text)
        abstract = self.extract_abstract(text)
        sections = self.extract_sections(text)
        references = self.extract_references(text)

        info = PaperInfo(
            title=title,
            abstract=abstract,
            sections=sections,
            references=references,
            raw_text=text,
        )
        logger.info(
            f"论文处理完成: {title}, {len(sections)} 个章节, {len(references)} 条引用"
        )
        return info

    def extract_key_points(self, paper: PaperInfo) -> List[str]:
        """从论文中提取关键观点"""
        points = []

        if paper.abstract:
            sentences = re.split(r'(?<=[.。])\s*', paper.abstract)
            for sent in sentences:
                if any(
                    kw in sent.lower()
                    for kw in [
                        "propose",
                        "present",
                        "introduce",
                        "achieve",
                        "提出",
                        "实现",
                    ]
                ):
                    points.append(sent.strip())

        # 从结论中提取
        for section in paper.sections:
            if "conclusion" in section["title"].lower() or "结论" in section["title"]:
                sentences = re.split(r'(?<=[.。])\s*', section["content"])
                for sent in sentences[:3]:
                    if len(sent.strip()) > 20:
                        points.append(sent.strip())

        return points[:5]
