import os
import time
import random
import glob
import nbformat

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from nbconvert.preprocessors import ExecutePreprocessor, CellExecutionError

@dataclass
class NotebookJob:
    notebook_path: str
    required_csv: List[str]

@dataclass
class JobResult:
    notebook_path: str
    success: bool
    attempts: int
    error: Optional[str]
    missing_csv: List[str]

def exponential_backoff_sleep(
        attempt: int,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        jitter: float = 0.25
) -> None:
    """
    attempt: 1,2,3,...
    delay = min(max_delay, base_delay * 2^(attempt-1)) * random_jitter
    """
    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
    # jitter factor around 1.0(e.g. 0.75 to 1.25 if jitter=0.25)
    jitter_factor = 1.0 + random.uniform(-jitter, jitter)
    time.sleep(max(0.0, delay * jitter_factor))

def file_exists(path: str) -> bool:
    return os.path.isfile(path)

def missing_files(paths: List[str]) -> List[str]:
    return [p for p in paths if not file_exists(p)]

def execute_notebook(
        notebook_path: str,
        timeout: int = 1800,
        kernel_name: str = 'python3'
) -> None:
    """
    
    """