# src/filtering/sentence_transformer_filter.py
import logging
from typing import Any, Dict, List, Optional

import torch
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

from src.filtering.base_filter import BaseFilter
from src.paper import Paper

logger = logging.getLogger(__name__)


class SentenceTransformerFilter(BaseFilter):
    """Filters papers based on semantic similarity using Sentence Transformers."""

    DEFAULT_MODEL = "all-MiniLM-L6-v2"
    DEFAULT_THRESHOLD = 0.65
    DEFAULT_TARGET_TEXT = "scientific research papers"
    DEFAULT_BATCH_SIZE = 32  # Default batch size for encoding

    def __init__(self):
        self.model: Optional[SentenceTransformer] = None
        self.target_embeddings: Optional[torch.Tensor] = None
        self.model_name: str = self.DEFAULT_MODEL
        self.similarity_threshold: float = self.DEFAULT_THRESHOLD
        self.target_texts: List[str] = [self.DEFAULT_TARGET_TEXT]
        self.device: Optional[str] = None
        self.batch_size: int = self.DEFAULT_BATCH_SIZE
        self.configured = False

    def configure(self, config: Dict[str, Any]):
        """Configures the filter with necessary parameters."""
        filter_config = config.get("relevance_checker", {}).get("sentence_transformer_filter", {})

        self.model_name = filter_config.get("model_name", self.DEFAULT_MODEL)
        self.similarity_threshold = float(filter_config.get("similarity_threshold", self.DEFAULT_THRESHOLD))
        raw_targets = filter_config.get("target_texts", [self.DEFAULT_TARGET_TEXT])
        self.device = filter_config.get("device")  # Can be None
        self.batch_size = int(filter_config.get("batch_size", self.DEFAULT_BATCH_SIZE))  # Read batch_size

        if isinstance(raw_targets, str):
            self.target_texts = [raw_targets]
        elif isinstance(raw_targets, list):
            self.target_texts = raw_targets
        else:
            logger.warning(f"Invalid format for target_texts. Using default: '{self.DEFAULT_TARGET_TEXT}'")
            self.target_texts = [self.DEFAULT_TARGET_TEXT]

        logger.info(
            f"SentenceTransformerFilter configured: Model='{self.model_name}', "
            f"Threshold={self.similarity_threshold}, Targets={len(self.target_texts)}, "
            f"Device='{self.device or 'auto'}', BatchSize={self.batch_size}"  # Add batch size to log
        )
        self._load_model_and_encode_targets()
        self.configured = True

    def _load_model_and_encode_targets(self):
        """Loads the Sentence Transformer model and pre-computes target embeddings."""
        try:
            logger.info(f"Loading Sentence Transformer model: '{self.model_name}'...")
            self.model = SentenceTransformer(self.model_name, device=self.device)
            logger.info(f"Model '{self.model_name}' loaded successfully.")

            if self.target_texts:
                logger.info(f"Encoding {len(self.target_texts)} target text(s)...")
                self.target_embeddings = self.model.encode(
                    self.target_texts, convert_to_tensor=True, show_progress_bar=False
                )
                logger.info("Target text(s) encoded successfully.")
            else:
                logger.warning("No target texts provided for SentenceTransformerFilter.")
                self.target_embeddings = None

        except Exception as e:
            logger.error(f"Failed to load model '{self.model_name}' or encode targets: {e}", exc_info=True)
            self.model = None
            self.target_embeddings = None

    def filter(self, papers: List[Paper]) -> List[Paper]:
        """Filters papers based on abstract similarity to target texts."""
        if not self.configured:
            logger.error("SentenceTransformerFilter not configured. Call configure() first.")
            return []
        if not self.model or self.target_embeddings is None:
            logger.error("Sentence Transformer model or target embeddings not loaded. Cannot filter.")
            return []
        if not papers:
            return []

        relevant_papers: List[Paper] = []
        abstracts = [p.abstract for p in papers if p.abstract]
        papers_with_abstracts = [p for p in papers if p.abstract]

        if not abstracts:
            logger.warning("No papers with abstracts found to filter with SentenceTransformerFilter.")
            return []

        logger.info(f"Encoding {len(abstracts)} paper abstracts... (Batch size: {self.batch_size})")
        try:
            paper_embeddings = self.model.encode(
                abstracts,
                convert_to_tensor=True,
                show_progress_bar=True,
                batch_size=self.batch_size,  # Use configured batch_size
            )

            # Calculate cosine similarities
            # Shape: (num_papers, num_targets)
            similarities = cos_sim(paper_embeddings, self.target_embeddings)

            for i, paper in enumerate(papers_with_abstracts):
                # Find the max similarity across all target texts for this paper
                max_similarity = torch.max(similarities[i]).item()

                if max_similarity >= self.similarity_threshold:
                    paper.similarity_score = round(max_similarity, 3)  # Store score
                    # Find which target text had the highest similarity (optional info)
                    best_target_index = torch.argmax(similarities[i]).item()
                    paper.matched_target = self.target_texts[best_target_index]
                    relevant_papers.append(paper)
                    logger.debug(
                        f"Paper '{paper.id}' relevant (Score: {max_similarity:.3f}, Target: '{paper.matched_target}')"
                    )
                else:
                    logger.debug(f"Paper '{paper.id}' not relevant (Max Score: {max_similarity:.3f})")

        except Exception as e:
            logger.error(f"Error during abstract encoding or similarity calculation: {e}", exc_info=True)
            # Decide how to handle: return empty, return all, etc.? Returning empty for now.
            return []

        logger.info(f"SentenceTransformerFilter found {len(relevant_papers)} relevant papers.")
        return relevant_papers
