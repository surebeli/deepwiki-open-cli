from dataclasses import dataclass


@dataclass
class WikiPage:
    title: str
    content: str


@dataclass
class WikiResult:
    title: str
    pages: list[WikiPage]


@dataclass
class AnswerSource:
    file_path: str
    chunk_preview: str
    relevance_score: float


@dataclass
class AskResult:
    answer: str
    sources: list[AnswerSource]
    metadata: dict[str, object]


@dataclass
class ResearchIteration:
    iteration: int
    question: str
    findings: str
    follow_up_questions: list[str]


@dataclass
class ResearchResult:
    topic: str
    summary: str
    iterations: list[ResearchIteration]
    conclusion: str
    sources: list[AnswerSource]
    metadata: dict[str, object]
