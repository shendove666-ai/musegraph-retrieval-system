"""Encode passages with a SentenceTransformer and retain matching text spans."""

from collections.abc import Sequence
from threading import RLock

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_REVISION = "c9745ed1d9f207416be6d2e6f8de32d1f16199bf"


class SemanticUnavailable(RuntimeError):
    """Report an inaccessible embedding dependency or model."""


class SentenceEncoder:
    def __init__(self, model_name: str, revision: str | None = None):
        self.model_name = model_name
        self.revision = revision or (DEFAULT_REVISION if model_name == DEFAULT_MODEL else None)
        self._model = None
        self._lock = RLock()

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(
                    self.model_name, revision=self.revision, trust_remote_code=False
                )
            except Exception as error:
                raise SemanticUnavailable(
                    "The semantic model could not be loaded. Install the semantic extra "
                    "and check the model path or Hugging Face connection."
                ) from error
        return self._model

    def passages(self, text: str) -> list[str]:
        with self._lock:
            model = self._load()
            tokenizer = model.tokenizer
            capacity = model.max_seq_length - tokenizer.num_special_tokens_to_add()
            width = min(128, capacity)
            if not tokenizer.is_fast or width < 2:
                raise SemanticUnavailable("The semantic model requires a fast tokenizer and at least two input tokens.")
            offsets = tokenizer(
                text, add_special_tokens=False, return_offsets_mapping=True,
                truncation=False, verbose=False,
            )["offset_mapping"]
        if not offsets:
            return [text]
        stride = width - min(24, width // 4)
        passages = []
        for start in range(0, len(offsets), stride):
            end = min(start + width, len(offsets))
            passages.append(text[offsets[start][0]:offsets[end - 1][1]])
            if end == len(offsets):
                break
        return passages

    def encode(self, texts: Sequence[str]):
        with self._lock:
            model = self._load()
            try:
                return model.encode(
                    list(texts), batch_size=32, normalize_embeddings=True, show_progress_bar=False
                )
            except Exception as error:
                raise SemanticUnavailable("The semantic model could not encode the input.") from error


class SemanticIndex:
    def __init__(self, texts: list[str], encoder: SentenceEncoder):
        self.encoder = encoder
        self.passages = []
        self.ranges = []  # Half-open window indices for each original passage.
        for text in texts:
            start = len(self.passages)
            self.passages.extend(encoder.passages(text))
            self.ranges.append((start, len(self.passages)))
        self.embeddings = encoder.encode(self.passages)

    def score(self, query: str) -> list[tuple[float, str]]:
        query_vector = self.encoder.encode([query])[0]
        similarities = self.embeddings @ query_vector
        passage_scores = []
        for start, end in self.ranges:
            best_window = start + int(similarities[start:end].argmax())
            score = max(0.0, min(1.0, float(similarities[best_window])))
            passage_scores.append((score, self.passages[best_window]))
        return passage_scores
