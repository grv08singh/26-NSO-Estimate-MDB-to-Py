from dataclasses import dataclass
from pathlib import Path

@dataclass
class DataIngestionConfig:
    root_dir: Path
    local_data_file: Path
    raw_data_file: Path
    src_chatwords_file: Path
    dest_chatwords_file: Path

@dataclass(frozen=True)
class DataPreProcessingConfig:
    root_dir: Path
    raw_data_file: Path
    chatwords_file: Path
    preprocessed_data: Path
    X_path: Path
    y_path: Path

@dataclass(frozen=True)
class DataProcessingConfig:
    root_dir: Path
    model_dir: Path
    X_path: Path
    word2idx_path: Path
    trained_emb_model: Path
    bert_emb_model: Path
    word_pair_emb: Path
    emb_matrix: Path
    emb_data_own: Path
    q1_emb_own: Path
    q2_emb_own: Path
    emb_data_bert: Path
    q1_emb_bert: Path
    q2_emb_bert: Path
    emb_min_token_count: int
    emb_max_words: int
    emb_window_size: int
    emb_dim: int
    emb_neg_samples: int
    emb_batch_size: int
    emb_epochs: int
    own_emb_model: bool